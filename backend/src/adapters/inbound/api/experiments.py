"""
Experiment API routes for RL optimization.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class CreateExperimentRequest(BaseModel):
    name: str
    parameter_space: dict
    max_trials: int = 50
    description: str = ""


@router.post("")
async def create_experiment(body: CreateExperimentRequest, request: Request):
    service = request.app.state.container.experiment_service()
    experiment = await service.create_experiment(
        name=body.name,
        parameter_space=body.parameter_space,
        max_trials=body.max_trials,
        description=body.description,
    )
    return {"experiment_id": experiment.id, "name": experiment.name}


@router.get("/{experiment_id}/results")
async def get_results(experiment_id: str, request: Request):
    service = request.app.state.container.experiment_service()
    return await service.get_experiment_results(experiment_id)


@router.get("/{experiment_id}/convergence")
async def get_convergence(experiment_id: str, request: Request):
    service = request.app.state.container.experiment_service()
    return await service.get_convergence_data(experiment_id)


@router.get("/{experiment_id}/parameters")
async def get_parameter_importance(experiment_id: str, request: Request):
    service = request.app.state.container.experiment_service()
    return await service.get_parameter_importance(experiment_id)


@router.post("/compare")
async def compare_experiments(body: dict, request: Request):
    service = request.app.state.container.experiment_service()
    ids = body.get("experiment_ids", [])
    return await service.compare_experiments(ids)
