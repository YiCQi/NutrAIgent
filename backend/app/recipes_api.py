from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import recipes
from .deps import get_conn

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


class IngredientIn(BaseModel):
    food_id: int
    grams: float = Field(gt=0, le=20000)


class RecipeIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    ingredients: list[IngredientIn] = Field(min_length=1, max_length=40)
    yield_g: float | None = Field(None, gt=0, le=50000)  # cooked weight; default = sum of ingredients
    notes: str = Field("", max_length=1000)


@router.get("")
def list_recipes(conn=Depends(get_conn)):
    return recipes.list_all(conn)


@router.post("", status_code=201)
def create_recipe(body: RecipeIn, conn=Depends(get_conn)):
    try:
        rid = recipes.create(conn, body.name, [i.model_dump() for i in body.ingredients], body.yield_g, body.notes)
    except recipes.RecipeError as e:
        raise HTTPException(409, str(e))
    return recipes.get(conn, rid)


@router.get("/{rid}")
def get_recipe(rid: int, conn=Depends(get_conn)):
    try:
        return recipes.get(conn, rid)
    except KeyError:
        raise HTTPException(404, "recipe not found")


@router.put("/{rid}")
def update_recipe(rid: int, body: RecipeIn, conn=Depends(get_conn)):
    try:
        recipes.update(conn, rid, body.name, [i.model_dump() for i in body.ingredients], body.yield_g, body.notes)
    except KeyError:
        raise HTTPException(404, "recipe not found")
    except recipes.RecipeError as e:
        raise HTTPException(409, str(e))
    return recipes.get(conn, rid)


@router.delete("/{rid}", status_code=204)
def delete_recipe(rid: int, conn=Depends(get_conn)):
    try:
        recipes.delete(conn, rid)
    except KeyError:
        raise HTTPException(404, "recipe not found")
    except recipes.RecipeError as e:
        raise HTTPException(409, str(e))
