#!/bin/bash
# MySQL 컨테이너가 "처음" 초기화될 때(데이터 볼륨이 비어있을 때)만 자동 실행된다
# (공식 mysql 이미지의 /docker-entrypoint-initdb.d/ 컨벤션).
#
# docker-compose.yml의 MYSQL_DATABASE(=${DB_NAME})는 앱이 실제로 쓰는 DB만 자동 생성/권한부여되므로,
# pytest가 쓰는 별도의 "test" DB는 여기서 만들고 같은 앱 계정에 권한을 준다.
# (app/tests/conftest.py의 TEST_DATABASE_URL과 짝 — DB 이름은 "test"로 고정)
set -e

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<-EOSQL
    CREATE DATABASE IF NOT EXISTS test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    GRANT ALL PRIVILEGES ON test.* TO '${MYSQL_USER}'@'%';
    FLUSH PRIVILEGES;
EOSQL
