import random
import time
import jwt


class JTI:

    @staticmethod
    def get_hs_key(client_id, client_secret, token_type, algorithm):
        token = None
        if token_type == "JTI":
            current_epoch_seconds = int(time.time())
            epoch_time = current_epoch_seconds + 84000
            jti = random.randint(1, 2**31 - 1)
            key = client_secret.encode()

            if algorithm == "HS256":
                token = jwt.encode(
                    {
                        "exp": epoch_time,
                        "jti": jti,
                        "appId": client_id
                    },
                    key,
                    algorithm="HS256"
                )
            elif algorithm == "HS512":
                token = jwt.encode(
                    {
                        "exp": epoch_time,
                        "jti": jti,
                        "appId": client_id
                    },
                    key,
                    algorithm="HS512"
                )
        elif token_type == "JWT":
            key = client_secret.encode()
            if algorithm == "HS256":
                token = jwt.encode(
                    {
                        "sub": "123456789",
                        "appId": client_id
                    },
                    key,
                    algorithm="HS256"
                )
            elif algorithm == "HS512":
                token = jwt.encode(
                    {
                        "sub": "123456789",
                        "appId": client_id
                    },
                    key,
                    algorithm="HS512"
                )
        return token


if __name__ == "__main__":
    jwt_jti_hs = JTI.get_hs_key(
        "cs-10ead778-9d02-56b8-a512-345628f4c4df",
        "FeX8hZvknkkIJEYGUzbqZHHr/neabc6FcgJxV3ir6xM=",
        "JWT",
        "HS256"
    )
    print(jwt_jti_hs)
