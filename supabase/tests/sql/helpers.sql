create function pg_temp.assert_true(value boolean, message text)
returns void language plpgsql as $$
begin
  if value is distinct from true then raise exception '%', message; end if;
end $$;

create function pg_temp.expect_error(command text, expected_state text)
returns void language plpgsql as $$
begin
  begin
    execute command;
  exception when others then
    if sqlstate = expected_state then return; end if;
    raise;
  end;
  raise exception 'expected SQLSTATE %, command succeeded: %', expected_state, command;
end $$;

-- Generated UUIDs and reserved email addresses avoid collisions with real users.
create temporary table auth_test_ids (email_user uuid, phone_user uuid);
insert into auth_test_ids values (gen_random_uuid(), gen_random_uuid());
grant select on auth_test_ids to anon, authenticated;
