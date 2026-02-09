"""PostgreSQL implementation of ExperimentRepositoryPort using SQLAlchemy async."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import relationship

from backend.src.core.entities.content_type import ContentType
from backend.src.core.entities.experiment import Experiment, ExperimentStatus, Trial
from backend.src.core.value_objects.reward_signal import RewardSignal
from backend.src.infrastructure.database import Base

logger = logging.getLogger(__name__)


class TrialModel(Base):  # type: ignore[misc]
    """SQLAlchemy model for the ``trials`` table."""

    __tablename__ = "trials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(
        String(36), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    trial_num = Column(Integer, nullable=False)
    parameters = Column(JSON, nullable=False, default=dict)
    reward_total = Column(Float, nullable=True)
    reward_components = Column(JSON, nullable=True)
    reward_weights = Column(JSON, nullable=True)
    sub_metrics = Column(JSON, nullable=False, default=dict)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_entity(self) -> Trial:
        """Convert to domain :class:`Trial` entity."""
        reward: Optional[RewardSignal] = None
        if self.reward_total is not None:
            reward = RewardSignal(
                total=self.reward_total,
                components=self.reward_components or {},
                weights=self.reward_weights or {},
            )
        return Trial(
            trial_num=self.trial_num,
            parameters=self.parameters or {},
            reward=reward,
            sub_metrics=self.sub_metrics or {},
            timestamp=self.timestamp,
        )

    @classmethod
    def from_entity(cls, experiment_id: str, trial: Trial) -> TrialModel:
        """Create an ORM instance from a domain :class:`Trial` entity."""
        return cls(
            experiment_id=experiment_id,
            trial_num=trial.trial_num,
            parameters=trial.parameters,
            reward_total=trial.reward.total if trial.reward else None,
            reward_components=trial.reward.components if trial.reward else None,
            reward_weights=trial.reward.weights if trial.reward else None,
            sub_metrics=trial.sub_metrics,
            timestamp=trial.timestamp,
        )


class ExperimentModel(Base):  # type: ignore[misc]
    """SQLAlchemy model for the ``experiments`` table."""

    __tablename__ = "experiments"

    id = Column(String(36), primary_key=True)
    name = Column(String(256), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    content_type = Column(String(64), nullable=False, default=ContentType.GENERAL.value)
    parameter_space = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default=ExperimentStatus.CREATED.value)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    trial_rows = relationship(
        "TrialModel", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_entity(self) -> Experiment:
        """Convert to domain :class:`Experiment` entity."""
        trials = [t.to_entity() for t in (self.trial_rows or [])]
        best: Optional[Trial] = None
        for t in trials:
            if t.reward is not None and (best is None or t.reward.total > best.reward.total):  # type: ignore[union-attr]
                best = t

        return Experiment(
            id=self.id,
            name=self.name,
            description=self.description,
            content_type=ContentType(self.content_type),
            parameter_space=self.parameter_space or {},
            status=ExperimentStatus(self.status),
            trials=trials,
            best_trial=best,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, experiment: Experiment) -> ExperimentModel:
        """Create an ORM instance from a domain :class:`Experiment` entity."""
        return cls(
            id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            content_type=experiment.content_type.value,
            parameter_space=experiment.parameter_space,
            status=experiment.status.value,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
        )


class PostgresExperimentRepository:
    """Implements :class:`ExperimentRepositoryPort` backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- ExperimentRepositoryPort implementation --------------------------------

    async def save(self, experiment: Experiment) -> Experiment:
        """Insert or update an experiment (without nested trials)."""
        experiment.updated_at = datetime.utcnow()
        model = ExperimentModel.from_entity(experiment)
        merged = await self._session.merge(model)
        await self._session.commit()
        logger.debug("Saved experiment %s to PostgreSQL", experiment.id)
        return merged.to_entity()

    async def get_by_id(self, experiment_id: str) -> Optional[Experiment]:
        """Fetch an experiment with all its trials."""
        result = await self._session.execute(
            select(ExperimentModel).where(ExperimentModel.id == experiment_id)
        )
        row = result.scalars().first()
        if row is None:
            logger.debug("Experiment %s not found in PostgreSQL", experiment_id)
            return None
        return row.to_entity()

    async def list_all(self) -> list[Experiment]:
        """Return all experiments ordered by creation date descending."""
        result = await self._session.execute(
            select(ExperimentModel).order_by(ExperimentModel.created_at.desc())
        )
        return [row.to_entity() for row in result.scalars().all()]

    async def add_trial(self, experiment_id: str, trial: Trial) -> None:
        """Persist a trial result for an existing experiment."""
        trial_model = TrialModel.from_entity(experiment_id, trial)
        self._session.add(trial_model)
        await self._session.commit()
        logger.debug(
            "Added trial #%d to experiment %s in PostgreSQL",
            trial.trial_num,
            experiment_id,
        )
