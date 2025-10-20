# Firetower

More docs to come eventually :')

## Starting the dev database

```sh
docker-compose -f docker-compose.db.yml
uv run manage.py migrate
```

You can inspect the database directly with adminer at http://localhost:8089
