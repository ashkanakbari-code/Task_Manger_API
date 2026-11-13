from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Path,status
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Manager API")

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
    return task

@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_task(done: bool | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Task)
    if done is not None:
        query = query.filter(models.Task.done == done)
    return query.all()

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
    return task

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: Annotated[int, Path(gt=0)], db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    db.delete(task)
    db.commit()
    