from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` ADD `sns_id` VARCHAR(255);
        ALTER TABLE `users` ADD `refresh_token` VARCHAR(512);
        ALTER TABLE `users` ADD `sns_provider` VARCHAR(20) NOT NULL DEFAULT 'LOCAL';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` DROP COLUMN `sns_id`;
        ALTER TABLE `users` DROP COLUMN `refresh_token`;
        ALTER TABLE `users` DROP COLUMN `sns_provider`;"""


MODELS_STATE = (
    "eJztmFtP2zAUgP9KladNYqgNvY23FsroRNsJyjbBUOQmbmqR2CF2gArx32c7bZM4F1LEaI"
    "v20ibH5yTnfDkXJ0+aSyzo0P0O9JE50w4rTxoGLuQHyspeRQOeF8mFgIGJI1VBpDOhzAcm"
    "49IpcCjkIgtS00ceQwRzKQ4cRwiJyRURtiNRgNFdAA1GbMhm0OcL1zdcjLAFHyFdnnq3xh"
    "RBx0q4iixxbyk32NyTsj5mJ1JR3G1imMQJXBwpe3M2I3iljTATUhti6AMGxeWZHwj3hXeL"
    "OJcRhZ5GKqGLMRsLTkHgsFi4JRmYBAt+3BsqA7TFXb7otXqr3j5o1ttcRXqykrSew/Ci2E"
    "NDSWA41p7lOmAg1JAYI2730KfCpRS8oxnws+nFTBSE3HEV4RJYEcOlIIIYJc4bUXTBo+FA"
    "bDOR4HqjUcDsZ+f86LRz/olrfRbREJ7MYY4PF0t6uCbARiBFaawBcaG+mwBr1WoJgFwrF6"
    "BcSwLkd2QwrMEkxO8Xo2E2xJiJAvIS8wCvLWSyvYqDKLvZTqwFFEXUwmmX0jsnDu/ToPNb"
    "5Xp0NupKCoQy25dXkRfocsaiZU5vY8UvBBNg3j4A3zJSK0QnebrpJVd3VQnAwJasRMQivs"
    "UQuaSyoaeGi5QXjpaAa9DtmixdZH+g4fJV1w8OWnr1oNlu1FutRru6mjLppaJx0+1/ExMn"
    "kZsvjyDoAuSs0ztXBrvZPetlmmc9v3fWU61zBugMWoYHKH0gfka+5rPMMN1NqjW9XWYm6e"
    "38mSTWkmDl/xo0l/q7iVAvk5h6fmLqqcTkEVthe08T7OHAlRT73CWATZiiGVlvmKc26Jz1"
    "Divi9w8+6YVn4b/2Cs7NEpibuZSbKuQJ8tnMAvM05mMOJztR4zYKXN6nIUMu3BcH25m2Bf"
    "yOO+Oewsfj0UGDZ9skLxWzGal2u1nUtVqZtljL74o1Nd8QNfgmDN1ndMYuIQ4EOGdjFLdT"
    "YE644b+iudo0vXWudUejs8QWvdtXNj/Dy0G3x/FKulwJscSeKMnUclHGe/iLSJdm70h03d"
    "33RpBSTA3PJ/codwJlM1Xt3q/stbPRUUeGv6XjXKDJeh0qhpn5QlQO46J0P9aXIgdQZjjE"
    "zqr248XwzaaZtCya2+JgK/kW4Bz3B72LcWfwI9EAxEAXK7qUzhVpap+0ukjlV398WhGnla"
    "vRsKd+HVnpja804RMIGDEweeD9NB72UrwUJR6kD6f8ajODkVu41hfUlOFOFkejppcoDq6V"
    "WxxyTfkK6EMRsQEyPgQWF0fS8g2KYxNbNx6DNcLOfPF4d6RaFplYWCyBZ73ywSYt/z/YjT"
    "5Y6fxGPyk//wX2GicW"
)
