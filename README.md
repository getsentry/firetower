# Firetower

More docs to come eventually :')

## Starting the dev database

```sh
cp config.example.toml config.toml
# Edit config.toml to contain the values you need
docker compose -f docker-compose.db.yml up -d
uv run manage.py migrate
```

You can inspect the database directly with adminer at http://localhost:8089
