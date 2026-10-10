from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import httpx

from backend.app.domain import (
    IngredientRecord, MealPlanItemRecord, MealPlanRecord, NutritionValues,
    ProfileRecord, RecipeIngredientRecord, RecipeRecord,
)
from backend.app.repositories.base import RepositoryError


def json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_value(item) for item in value]
    return value


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def valid_uuid(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


class SupabaseRepository:
    """Request-scoped Data API adapter. RLS runs as the authenticated user."""

    def __init__(self, url, key, token, user_id, *, timeout=10, client=None):
        self.user_id = user_id
        self.client = client or httpx.Client(timeout=timeout)
        self.owns_client = client is None
        self.url = url.rstrip("/") + "/rest/v1/"
        self.headers = {"apikey": key, "Authorization": f"Bearer {token}", "Prefer": "return=representation"}
        self._ingredients = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.owns_client:
            self.client.close()

    def request(self, method, path, *, params=None, data=None):
        try:
            response = self.client.request(method, self.url + path, headers=self.headers, params=params, json=json_value(data))
        except httpx.HTTPError as exc:
            raise RepositoryError(503, "数据服务暂不可用，请重新读取以确认保存结果") from exc
        if response.is_error:
            try:
                code = response.json().get("code", "")
            except ValueError:
                code = ""
            if code == "23505":
                raise RepositoryError(409, "记录已存在，请重新加载")
            if code == "PT409":
                raise RepositoryError(409, "计划已被修改，请重新加载后再保存")
            if code == "PT404":
                raise RepositoryError(404, "记录不存在")
            if response.status_code == 401:
                raise RepositoryError(401, "登录凭证无效或已过期")
            if code in {"23502", "23503", "23514", "22023", "22P02", "22003"}:
                raise RepositoryError(422, "保存内容不符合数据约束，请检查后重试")
            if response.status_code == 403:
                raise RepositoryError(403, "没有访问该记录的权限")
            raise RepositoryError(503, "数据服务暂不可用，请稍后重试")
        return response.json() if response.content else None

    def _check_user(self, user_id):
        if user_id != self.user_id:
            raise RepositoryError(404, "记录不存在")

    def _catalog(self):
        if self._ingredients is None:
            rows = self.request("GET", "ingredients", params={"select": "*", "order": "id", "limit": "1000"})
            self._ingredients = {
                row["id"]: IngredientRecord(
                    row["id"], row["name"], row["category"],
                    NutritionValues(*(Decimal(str(row[field])) for field in ("kcal_per_100g", "protein_per_100g", "carbs_per_100g", "fat_per_100g"))),
                    row["nutrition_basis"], row["is_active"],
                ) for row in rows
            }
        return self._ingredients

    def list_ingredients(self, query=None, category=None):
        return [item for item in self._catalog().values() if item.is_active
                and (not query or query.casefold() in item.name.casefold())
                and (not category or category == item.category)]

    def get_ingredient(self, ingredient_id, include_inactive=False):
        item = self._catalog().get(ingredient_id)
        return item if item and (item.is_active or include_inactive) else None

    @staticmethod
    def _recipe(row):
        return RecipeRecord(row["id"], row["user_id"], row["name"], row.get("description"),
                            [RecipeIngredientRecord(item["ingredient_id"], Decimal(str(item["raw_weight_g"]))) for item in row["recipe_ingredients"]],
                            timestamp(row.get("archived_at")))

    def list_recipes(self, user_id, include_archived=False):
        self._check_user(user_id)
        params = {"select": "*,recipe_ingredients(*)", "user_id": f"eq.{self.user_id}", "order": "created_at.desc,id"}
        if not include_archived:
            params["archived_at"] = "is.null"
        # Page explicitly rather than silently truncating a user's saved recipes.
        rows = []
        while True:
            page = self.request("GET", "recipes", params=params | {"limit": "500", "offset": str(len(rows))})
            rows.extend(page)
            if len(page) < 500:
                break
        return [self._recipe(row) for row in rows]

    def get_recipe(self, recipe_id):
        if not valid_uuid(recipe_id):
            return None
        rows = self.request("GET", "recipes", params={"select": "*,recipe_ingredients(*)", "id": f"eq.{recipe_id}", "user_id": f"eq.{self.user_id}"})
        return self._recipe(rows[0]) if rows else None

    def create_recipe(self, user_id, name, description, ingredients):
        self._check_user(user_id)
        recipe_id = self.request("POST", "rpc/save_recipe", data={"p_recipe_id": None, "p_name": name, "p_description": description, "p_ingredients": [asdict(item) for item in ingredients]})
        return self.get_recipe(recipe_id)

    def update_recipe(self, recipe, name, description, ingredients):
        self._check_user(recipe.user_id)
        self.request("POST", "rpc/save_recipe", data={"p_recipe_id": recipe.id, "p_name": name, "p_description": description, "p_ingredients": [asdict(item) for item in ingredients]})
        return self.get_recipe(recipe.id)

    def archive_recipe(self, recipe):
        self._check_user(recipe.user_id)
        self.request("PATCH", "recipes", params={"id": f"eq.{recipe.id}", "user_id": f"eq.{self.user_id}"}, data={"archived_at": datetime.now(timezone.utc)})
        return self.get_recipe(recipe.id)

    def save_profile(self, profile):
        self._check_user(profile.user_id)
        payload = asdict(profile)
        payload.pop("user_id")
        self.request("PATCH", "profiles", params={"id": f"eq.{self.user_id}"}, data=payload)
        saved = self.get_profile(self.user_id)
        if saved is None:
            raise RepositoryError(503, "个人资料未准备好，请稍后重试")
        return saved

    def get_profile(self, user_id):
        self._check_user(user_id)
        rows = self.request("GET", "profiles", params={"id": f"eq.{self.user_id}", "select": "*"})
        if not rows or rows[0].get("baseline_confirmed_at") is None:
            return None
        row = rows[0]
        return ProfileRecord(self.user_id, row["sex"], row["age"],
                             *(Decimal(str(row[field])) for field in ("height_cm", "weight_kg", "activity_factor")),
                             row["goal"], *(Decimal(str(row[field])) for field in ("target_kcal", "protein_g", "carbs_g", "fat_g")),
                             timestamp(row["baseline_confirmed_at"]))

    @staticmethod
    def _plan(row):
        items = []
        for item in sorted(row["meal_plan_items"], key=lambda value: (value["sort_order"], value["created_at"], value["id"])):
            manual = NutritionValues(*(Decimal(str(item[field])) for field in ("manual_kcal", "manual_protein_g", "manual_carbs_g", "manual_fat_g"))) if item["input_mode"] == "manual" else None
            items.append(MealPlanItemRecord(item["id"], date.fromisoformat(item["planned_date"]), item["meal_type"], item["input_mode"], item.get("recipe_id"), item.get("meal_name"), Decimal(str(item["quantity"])) if item.get("quantity") is not None else None, manual, item["sort_order"]))
        return MealPlanRecord(row["id"], row["user_id"], date.fromisoformat(row["week_start"]),
                              NutritionValues(*(Decimal(str(row[field])) for field in ("target_kcal", "target_protein_g", "target_carbs_g", "target_fat_g"))),
                              items, row["status"], row["updated_at"])

    def create_meal_plan(self, plan):
        self._check_user(plan.user_id)
        self.request("POST", "meal_plans", data={"id": plan.id, "user_id": self.user_id, "week_start": plan.week_start,
                     "target_kcal": plan.target.kcal, "target_protein_g": plan.target.protein_g, "target_carbs_g": plan.target.carbs_g, "target_fat_g": plan.target.fat_g})
        return self.get_meal_plan(self.user_id, plan.week_start)

    def get_meal_plan(self, user_id, week_start):
        self._check_user(user_id)
        rows = self.request("GET", "meal_plans", params={"select": "*,meal_plan_items(*)", "user_id": f"eq.{self.user_id}", "week_start": f"eq.{week_start.isoformat()}"})
        return self._plan(rows[0]) if rows else None

    @staticmethod
    def _item_json(item):
        payload = asdict(item)
        manual = payload.pop("manual_nutrition")
        if manual:
            payload.update({f"manual_{key}": value for key, value in manual.items()})
        return payload

    def add_plan_item(self, plan, item):
        self.request("POST", "rpc/save_plan_items", data={"p_plan_id": plan.id, "p_items": [self._item_json(item)], "p_expected_revision": None, "p_append": True})
        return self.get_meal_plan(self.user_id, plan.week_start)

    def replace_plan_items(self, plan, items, expected_revision=None):
        self.request("POST", "rpc/save_plan_items", data={"p_plan_id": plan.id, "p_items": [self._item_json(item) for item in items], "p_expected_revision": expected_revision})
        return self.get_meal_plan(self.user_id, plan.week_start)
