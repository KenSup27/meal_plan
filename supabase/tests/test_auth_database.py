def test_email_and_phone_registration_lifecycle(run_database_sql):
    run_database_sql("auth_lifecycle.sql")


def test_anonymous_owner_and_cross_user_permissions(run_database_sql):
    run_database_sql("auth_permissions.sql")


def test_registered_user_database_workflow(run_database_sql):
    run_database_sql("database_integration.sql")


def test_recipe_deletion_and_ingredient_reassignment(run_database_sql):
    run_database_sql("recipe_integrity.sql")


def test_plan_week_changes_preserve_existing_items(run_database_sql):
    run_database_sql("plan_integrity.sql")
