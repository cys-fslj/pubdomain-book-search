import os

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

import db

app = FastAPI(title="公版书元数据搜索")
BASE = os.path.dirname(os.path.abspath(__file__))


def escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.get("/api/search")
def api_search(q: str = Query(..., min_length=1, max_length=100), limit: int = Query(50, ge=1, le=200)):
    conn = db.connect()
    like = f"%{escape_like(q)}%"
    rows = conn.execute(
        "SELECT title, author, source_name, source_url FROM books "
        "WHERE title LIKE ? ESCAPE '\\' OR author LIKE ? ESCAPE '\\' "
        "ORDER BY "
        "CASE WHEN title = ? THEN 0 WHEN title LIKE ? ESCAPE '\\' THEN 1 ELSE 2 END, title "
        "LIMIT ?",
        (like, like, q, f"{escape_like(q)}%", limit),
    ).fetchall()
    conn.close()
    return {"query": q, "total": len(rows), "results": [dict(r) for r in rows]}


@app.get("/")
def index():
    return FileResponse(os.path.join(BASE, "static", "index.html"))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
