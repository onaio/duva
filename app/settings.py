from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Duva"
    app_description: str = ""
    app_version: str = "v0.0.5"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: str = "postgres://duva:duva@127.0.0.1/duva"
    debug: bool = True
    sentry_dsn: str = ""
    session_same_site: str = "none"
    # How long force update is locked after an update is completed
    force_update_cooldown: int = 10
    # How long download URLs for HyperFiles should last
    download_url_lifetime: int = 3600
    # Generate secret key using:
    #  dd if=/dev/urandom bs=32 count=1 2>/dev/null | openssl base64
    secret_key: str = "xLLwpyLgT0YumXu77iDYX+HDVBX6djFFVbAWPhhHAHY="
    enable_secure_sessions: bool = False
    # check_same_thread: False is only needed for SQLite
    # https://fastapi.tiangolo.com/tutorial/sql-databases/#note
    db_connect_args: dict = {}
    media_path: str = "/app/media"
    s3_bucket: str = "hypermind-mvp"
    s3_region: str = "eu-west-1"
    # For more on tokens, head here:
    # https://help.tableau.com/current/server/en-us/security_personal_access_tokens.htm
    tableau_server_address: str = ""
    tableau_site_name: str = ""
    tableau_token_name: str = ""
    tableau_token_value: str = ""
    redis_url: str = "redis://cache"
    redis_host: str = "cache"
    redis_port: int = 6379
    redis_db: int = 0
    # CORS Configuration
    cors_allowed_origins: list = ["http://localhost:3000", "http://localhost:8000"]
    cors_allow_credentials: bool = True
    cors_allowed_methods: list = ["*"]
    cors_allowed_headers: list = ["*"]
    cors_max_age: int = -1
    # HyperFile job settings
    job_failure_limit: int = 5
    schedule_all_active: bool = False


settings = Settings()
