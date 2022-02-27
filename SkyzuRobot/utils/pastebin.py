import base64
import json
import socket
import typing
import zlib
from asyncio import get_running_loop
from functools import partial
from urllib.parse import urljoin, urlparse, urlunparse

import base58
import requests
from Crypto import Hash, Protocol, Random
from Crypto.Cipher import AES

from SkyzuRobot.utils.http import post

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.104 Safari/537.36",
    "content-type": "application/json",
}


BASE = "https://batbin.me/"


def _netcat(host, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.sendall(content.encode())
    s.shutdown(socket.SHUT_WR)
    while True:
        data = s.recv(4096).decode("utf-8").strip("\n\x00")
        if not data:
            break
        return data
    s.close()


async def paste(content):
    loop = get_running_loop()
    link = await loop.run_in_executor(None, partial(_netcat, "ezup.dev", 9999, content))
    return link


async def hpaste(content: str):
    resp = await post(f"{BASE}api/v2/paste", data=content)
    if not resp["success"]:
        return
    return BASE + resp["message"]


def upload_text(data: str) -> typing.Optional[str]:
    passphrase = Random.get_random_bytes(32)
    salt = Random.get_random_bytes(8)
    key = Protocol.KDF.PBKDF2(
        passphrase, salt, 32, 100000, hmac_hash_module=Hash.SHA256
    )
    compress = zlib.compressobj(wbits=-15)
    paste_blob = (
        compress.compress(json.dumps({"paste": data}, separators=(",", ":")).encode())
        + compress.flush()
    )
    cipher = AES.new(key, AES.MODE_GCM)
    paste_meta = [
        [
            base64.b64encode(cipher.nonce).decode(),
            base64.b64encode(salt).decode(),
            100000,
            256,
            128,
            "aes",
            "gcm",
            "zlib",
        ],
        "syntaxhighlighting",
        0,
        0,
    ]
    cipher.update(json.dumps(paste_meta, separators=(",", ":")).encode())
    ct, tag = cipher.encrypt_and_digest(paste_blob)
    resp = requests.post(
        "https://bin.nixnet.services",
        headers={"X-Requested-With": "JSONHttpRequest"},
        data=json.dumps(
            {
                "v": 2,
                "adata": paste_meta,
                "ct": base64.b64encode(ct + tag).decode(),
                "meta": {"expire": "1week"},
            },
            separators=(",", ":"),
        ),
    )
    data = resp.json()
    url = list(urlparse(urljoin("https://bin.nixnet.services", data["url"])))
    url[5] = base58.b58encode(passphrase).decode()
    return urlunparse(url)
