from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` ADD `agreed_terms_at` DATETIME(6);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` DROP COLUMN `agreed_terms_at`;"""


MODELS_STATE = (
    "eJztmW1v0zAQgP9KlU8gAVqzvsG3ditQtLYIOkAMFLmJm1pL7BA7GxXaf+fstE3ivCydBm"
    "0RX9b2fJfcPb4XJ/tl+MzBHn/RxyGxl8arxi+DIh/DF23lWcNAQZDIpUCguadUUaIz5yJE"
    "tgDpAnkcg8jB3A5JIAijIKWR50khs0GRUDcRRZT8iLAlmIvFEoewcPUdxIQ6+Cfmm5/Btb"
    "Ug2HMyrhJH3lvJLbEKlGxExWulKO82t2zmRT5NlIOVWDK61SZUSKmLKQ6RwPLyIoyk+9K7"
    "dZybiGJPE5XYxZSNgxco8kQq3JoMbEYlP/CGqwBdeZfnZrPVbfVOO60eqChPtpLuXRxeEn"
    "tsqAhMZsadWkcCxRoKY8LtBodcupSDd7ZEYTG9lImGEBzXEW6AVTHcCBKISeI8EkUf/bQ8"
    "TF0hE9xstyuYfep/OHvb//AEtJ7KaBgkc5zjk/WSGa9JsAlIWRo7QFyrHyfA5slJDYCgVQ"
    "pQrWUBwh0FjmswC/Hdx+mkGGLKRAN5SSHAK4fY4lnDI1x8P0ysFRRl1NJpn/MfXhrek3H/"
    "i8717GI6UBQYF26orqIuMADGsmUurlPFLwVzZF/fotCxcivMZGW6+SXf9HUJoshVrGTEMr"
    "71ELnkqqHnhouSV46WCDT4YU2WAXH/oeHy0jRPT7vmyWmn1251u+3eyXbK5Jeqxs1g9EZO"
    "nExu3j+CsI+It0vv3BocZ/ds1WmerfLe2cq1ziXiS+xYAeL8loUF+VrOssD0OKk2zV6dmW"
    "T2ymeSXMuCVZ870NzoHydCs05imuWJaeYSEyJ24vaeJzikka8ojsAlRG2co5lY75mnMe5f"
    "DF815N9v9PUw/hV/Gg/g3KmBuVNKuaNDnpNQLB20ymM+BzjFiZq20eBCn8aC+PiF/HKYaV"
    "vB77w/G2p8AogOW5Bt87JULGak2x1nUTebddpis7wrNvV8I9yCQxi5KeiMA8Y8jGjJwSht"
    "p8Gcg+Gfork9ND12rg2m04vMEX0w0g4/k8vxYAh4FV1QIiJzJsoydXxS8Bx+L9KN2V8kuu"
    "vpey9IOeVWELIbUjqBipnqdn+v7I2L6VlfhX+g41yiKXocqoZZ+EBUD+O6dP+tN0Ue4sLy"
    "mFtU7efr4VtMM2tZNbfll4PkW4FzNhoPP8764/eZBiAHulwxlXSlSXPnpO1FGp9Hs7cN+b"
    "PxdToZ6m9Htnqzr4b0CUWCWZTdQj9Nh70Rb0SZjQzxAq62tAS7xju9Qc0ZHmVxtJtmjeIA"
    "rdLiUGvaa1TYIHgeFTj0YbYVvA2srpAC8/9lsucysUMs0T5gN7OWj7CR+ziNQwzOlHqrdR"
    "4dyc6uU75yY6PAeeDGZi3/b+xeN1Y5v9f/Etz9Bh8KvP8="
)
