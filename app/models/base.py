from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# - MySQL/PostgreSQL: BigInteger
# - SQLite: Integer
BIGINT_TYPE = BigInteger().with_variant(Integer, "sqlite")
