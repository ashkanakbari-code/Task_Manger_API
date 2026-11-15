import json
import logging
import redis

from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Path,status
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db
from redis_client import redis_client

logger = logging.getLogger(__name__)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Manager API")

CACHE_TTL = 60

def tasks_cache_key(done: bool | None) -> str:
    if done is None:
        return "tasks:all"
    return f"tasks:done:{str(done).lower()}"

def cache_get(key: str) -> str | None:
    try:
        return redis_client.get(key)
    except redis.RedisError:
        logger.warning("Redis unavailable, falling back to the database")
        return None

def cache_set(key: str, value: str) -> None:
    try:
        redis_client.set(key, value, ex=CACHE_TTL)
    except redis.RedisError:
        logger.warning("Redis unavailable, result was not cached")

def invalidate_tasks_cache() -> None:
    try:
        redis_client.delete("tasks:all", "tasks:done:ture", "tasks:done:false")
    except redis.RedisError:
        logger.warning("Redis unavailable, cache was not invalidated")

def get_task_or_404(db: Session, task_id: int) -> models.Task:
    task = db.get(models.Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/tasks", response_model=schemas.TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(data: schemas.TaskCreate, db: Session = Depends(get_db)):
    task = models.Task(**data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    invalidate_tasks_cache()
    return task

@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_task(done: bool | None = None, db: Session = Depends(get_db)):
    key = tasks_cache_key(done)

    cached = cache_get(key)
    if cached is not None:
        return json.loads(cached)
    
    query = db.query(models.Task)
    if done is not None:
        query = query.filter(models.Task.done == done)
    tasks = query.all()

    result = [schemas.TaskOut.model_validate(t).model_dump() for t in tasks]
    cache_set(key, json.dumps(result))
    return result

@app.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: Annotated[int, Path(gt=0)], db: Session = Depends(get_db)):
    return get_task_or_404(db, task_id)

@app.put("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: Annotated[int, Path(gt=0)],
    data: schemas.TaskUpdate,
    db: Session = Depends(get_db),
):
    task = get_task_or_404(db, task_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    invalidate_tasks_cache()
    return task

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: Annotated[int, Path(gt=0)], db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    db.delete(task)
    db.commit()
    invalidate_tasks_cache()
    