import json
from secrets import token_urlsafe

from fastapi import FastAPI, Cookie
from starlette.requests import Request
from starlette.responses import RedirectResponse
from aiohttp import client
from tortoise.contrib.fastapi import register_tortoise

from models import BrawlhallaUser

with open("config.json") as config_file:
    config = json.load(config_file)

app = FastAPI()

@app.get("/start_link")
async def discord_oauth_redir():
    state_key = token_urlsafe(20)
    response = RedirectResponse(
        f"https://discordapp.com/api/v7/oauth2/authorize?client_id={config['client_id']}&state={state_key}&redirect_uri={config['redirect_url']}&response_type=code&scope=identify%20connections&prompt=none",
        status_code=307
    )
    # We won't need this cookie 5 minutes later
    response.set_cookie(key="state_key", value=state_key, expires=300)
    return response


@app.get("/finish_link")
async def finish_link(error: str = None, code: str = None, state: str = None, request: Request = None, state_key: str = Cookie(None)):
    if error is not None:  # They must of denied the auth request if this errors
        return "You didn't grant us access"

    if state != state_key or code is None:
        return "Detected tampering with the request, linking denied"

    # we got a code, grab auth token
    session_pool = client.ClientSession()

    body = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "code": code,
        "redirect_uri": config["redirect_url"],
        "scope": "identify connections",
        "grant_type": "authorization_code"
    }

    async with session_pool.post("https://discordapp.com/api/v7/oauth2/token", data=body) as token_resp:
        token_return = await token_resp.json()
        access_token = token_return["access_token"]

    # Fetch user info
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    async with session_pool.get(f"https://discordapp.com/api/v6/users/@me", headers=headers) as resp:
        user_info = await resp.json()
        user_id = int(user_info["id"])

    async with session_pool.get("https://discordapp.com/api/v6/users/@me/connections", headers=headers) as resp:
        connections = await resp.json()
        found = False
        for connection in connections:
            if connection["type"] == "steam":
                async with session_pool.get(f"https://api.brawlhalla.com/search?steamid={connection['id']}&api_key={config['api_key']}") as bresp:
                    info = await bresp.json()
                    if "brawlhalla_id" in info:
                        found = True
                        await BrawlhallaUser.create(discord_id=user_id, brawlhalla_id=info["brawlhalla_id"])
                        break

        if found:
            return "Your brawlhalla account was successfully linked!"
        else:
            return "It doesn't have a steam account with brawlhalla linked to your discord account. Please either link one to your discord account and try again or use the <insert command here> command to link your brawlhalla account"
        


    await session_pool.close()

register_tortoise(
    app,
    db_url=config["db_url"],
    modules={"models": ["models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=5000, log_level="info", reload=True)
