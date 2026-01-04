import os
import json
import sys
import pathlib
from typing import Optional
import httpx
from fastapi import FastAPI, Depends, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = pathlib.Path(__file__).parent.resolve()
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

env_path = BACKEND_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)

import models, schemas
from database import SessionLocal, engine
from sqlalchemy import text
from datetime import datetime, timedelta


def normalize_due_date(d: Optional[str]) -> Optional[str]:
    if not d:
        return None
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%dT%H:%M:%S")
    if not isinstance(d, str):
        return None
    s = d.strip()
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        pass
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y.%m.%d"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if "%H" in fmt:
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return s


models.Base.metadata.create_all(bind=engine)

try:
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA table_info('todos')")).fetchall()
        cols = [r[1] for r in res]
        if 'priority' not in cols:
            conn.execute(text("ALTER TABLE todos ADD COLUMN priority INTEGER DEFAULT 0"))
except Exception:
    pass


app = FastAPI(title="NL Todo - FastAPI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = (
    "你是一个待办事项解析助手。从用户输入的自然语言生成一个 JSON。\n"
    "可能的行为（action）：'add' 表示添加待办；'delete' 表示删除待办（仅允许通过时间范围删除）。\n"
    "当 action='add' 时，返回字段: title(必填), description(可选), due_date(解析出的日期时间。规则：1. 优先提取明确时间点(如19:00)；2. 若仅有模糊时段(如早上/上午)设为12:00，(下午)设为18:00，(晚上)设为22:00；3. 若仅有日期无时间，设为23:59:59。格式 ISO8601), tags(数组，若无则空数组), priority(整数，数值越大优先级越高，范围为1-10)。\n"
    "当 action='delete' 时，返回字段: action='delete', start(开始时间 ISO8601 或 YYYY-MM-DD，必填), end(结束时间 ISO8601 或 YYYY-MM-DD，必填), keywords(可选，辅助说明)。\n"
    "总规则：尽量给出明确的时间范围用于删除。如果输入既含有添加也含删除意图，优先按用户整体意图处理。只输出纯 JSON，不要额外解释。\n"
    "特别注意：1. 一周的第一天是星期一，最后一天是星期日。2. '下周'或'下星期'是指当前日期所在周的下一周。例如若今天是周六，'下周五'是指下个日历周的周五（即下周一之后的周五）。"
)


async def call_deepseek_extract(text: str, reference_time: Optional[datetime] = None) -> Optional[dict]:
    if not DEEPSEEK_API_KEY:
        return None
    
    if reference_time is None:
        reference_time = datetime.now()
        
    current_time_str = reference_time.strftime("%Y-%m-%d %H:%M:%S")
    weekday_idx = reference_time.weekday()
    weekday_str = ["一", "二", "三", "四", "五", "六", "日"][weekday_idx]
    
    this_monday = reference_time - timedelta(days=weekday_idx)
    this_sunday = this_monday + timedelta(days=6)
    next_monday = this_monday + timedelta(days=7)
    next_sunday = next_monday + timedelta(days=6)
    
    this_monday_str = this_monday.strftime("%Y-%m-%d")
    this_sunday_str = this_sunday.strftime("%Y-%m-%d")
    next_monday_str = next_monday.strftime("%Y-%m-%d")
    next_sunday_str = next_sunday.strftime("%Y-%m-%d")
    
    dynamic_system_prompt = (
        f"{SYSTEM_PROMPT}\n"
        f"当前时间是：{current_time_str} (星期{weekday_str})。\n"
        f"日历定义：\n"
        f"- 本周范围：{this_monday_str} 至 {this_sunday_str}\n"
        f"- 下周范围：{next_monday_str} 至 {next_sunday_str}\n"
        f"请严格基于上述范围解析。例如用户说'下周五'，应在'下周范围'内寻找周五的日期。"
    )

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": dynamic_system_prompt},
            {"role": "user", "content": text},
        ],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                lines = [line for line in content.splitlines() if not line.strip().lower().startswith("```json")]
                content = "\n".join(lines).strip("`")
            try:
                obj = json.loads(content)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                return None
    except Exception:
        return None
    return None


async def call_deepseek_intent(text: str) -> Optional[dict]:
    if not DEEPSEEK_API_KEY:
        return None
    prompt = '''你是一个意图识别与时间抽取助手。对用户输入判断是创建待办还是删除待办。
输出 JSON，字段：intent ("create" 或 "delete"), 如果 intent=="create"，data 字段应包含 title, description, due_date (规则：1. 优先提取明确时间点(如19:00)；2. 若仅有模糊时段(如早上/上午)设为12:00，(下午)设为18:00，(晚上)设为22:00；3. 若仅有日期无时间，设为23:59:59), tags，
如果 intent=="delete"，则应包含 start 和 end（ISO 或 YYYY-MM-DD 格式，无法确定返回 null），只输出纯 JSON，不要额外解释。'''

    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    weekday_str = ["一", "二", "三", "四", "五", "六", "日"][datetime.now().weekday()]
    dynamic_prompt = f"{prompt}\n当前时间是：{current_time_str} (星期{weekday_str})。"

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": dynamic_prompt},
            {"role": "user", "content": text},
        ],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                lines = [line for line in content.splitlines() if not line.strip().lower().startswith("```json")]
                content = "\n".join(lines).strip("`")
            try:
                obj = json.loads(content)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                return None
    except Exception:
        return None
    return None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/todos", response_model=list[schemas.TodoRead])
def read_todos(db: Session = Depends(get_db)):
    todos = db.query(models.Todo).all()
    return [schemas.TodoRead.from_orm(t) for t in todos]


@app.get("/todos/date", response_model=list[schemas.TodoRead])
def read_todos_by_date(date: str, db: Session = Depends(get_db)):
    if not date:
        raise HTTPException(status_code=400, detail="Missing 'date' query parameter")
    todos = db.query(models.Todo).filter(models.Todo.due_date != None).filter(models.Todo.due_date.like(f"{date}%")).all()
    return [schemas.TodoRead.from_orm(t) for t in todos]


@app.post("/todos", response_model=schemas.TodoRead)
def create_todo(todo: schemas.TodoCreate, db: Session = Depends(get_db)):
    tags_csv = ",".join(todo.tags) if todo.tags else None
    due_date_norm = normalize_due_date(todo.due_date)
    dbobj = models.Todo(
        title=todo.title,
        description=todo.description,
        due_date=due_date_norm,
        tags=tags_csv,
        priority=(int(todo.priority) if todo.priority is not None else 0),
    )
    db.add(dbobj)
    db.commit()
    db.refresh(dbobj)
    return schemas.TodoRead.from_orm(dbobj)


@app.post("/todos/nl")
async def create_or_delete_todo_nl(payload: dict, db: Session = Depends(get_db)):
    text = payload.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' in payload")

    now = payload.get('now') or payload.get('current_time')
    augmented_text = text
    
    reference_time = None
    if now:
        try:
            if now.endswith('Z'):
                reference_time = datetime.fromisoformat(now[:-1])
            else:
                reference_time = datetime.fromisoformat(now)
        except Exception:
            pass
            
        augmented_text = f"{text}\n当前时间(ISO)：{now}\n说明：如果用户使用相对时间表达(例如 今天/明天/后天/下周)，请基于上述当前时间解析并在返回的 JSON 中填入具体的 due_date/start/end 字段。"
    
    parsed = await call_deepseek_extract(augmented_text, reference_time=reference_time)
    if not parsed:
        title = text
        description = None
        due_date = None
        tags = []
        tags_csv = None
        dbobj = models.Todo(title=title, description=description, due_date=due_date, tags=tags_csv, priority=0)
        db.add(dbobj)
        db.commit()
        db.refresh(dbobj)
        return schemas.TodoRead.from_orm(dbobj)

    action = parsed.get("action", "add").lower() if isinstance(parsed.get("action"), str) else "add"

    if action == 'delete':
        def mk_day_range(date_str: str):
            return f"{date_str}T00:00:00", f"{date_str}T23:59:59"

        start = parsed.get('start')
        end = parsed.get('end')
        if not start and not end:
            single = parsed.get('due_date') or parsed.get('date') or parsed.get('day')
            if single:
                if isinstance(single, str) and len(single) == 10 and single.count('-') == 2:
                    start, end = mk_day_range(single)
                else:
                    start = single
                    end = single
        if not start or not end:
            raise HTTPException(status_code=400, detail="Delete action requires a valid 'start'/'end' or a date/due_date to define the range")
        start = normalize_due_date(start) or start
        end = normalize_due_date(end) or end
        try:
            sel_sql = text("SELECT id, title FROM todos WHERE due_date IS NOT NULL AND datetime(due_date) >= datetime(:start) AND datetime(due_date) <= datetime(:end)")
            rows = db.execute(sel_sql, {"start": start, "end": end}).fetchall()
            deleted = []
            ids = [r[0] for r in rows]
            for r in rows:
                deleted.append({"id": r[0], "title": r[1]})
            if ids:
                id_list = tuple(ids)
                db.execute(text(f"DELETE FROM todos WHERE id IN ({', '.join([':id'+str(i) for i in range(len(id_list))])})"), {f"id{i}": id_list[i] for i in range(len(id_list))})
            db.commit()
        except Exception:
            q = db.query(models.Todo).filter(models.Todo.due_date != None).filter(models.Todo.due_date >= start).filter(models.Todo.due_date <= end)
            candidates = q.all()
            deleted = []
            for c in candidates:
                deleted.append({"id": c.id, "title": c.title})
                db.delete(c)
            db.commit()
        return {"deleted": deleted, "count": len(deleted)}

    title = parsed.get("title") or text
    description = parsed.get("description")
    due_date = normalize_due_date(parsed.get("due_date"))
    tags = parsed.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not isinstance(tags, list):
        tags = []

    tags_csv = ",".join(tags) if tags else None
    pr = parsed.get('priority') if isinstance(parsed, dict) else None
    try:
        pr_val = int(pr) if pr is not None else 0
    except Exception:
        pr_val = 0
    dbobj = models.Todo(title=title, description=description, due_date=due_date, tags=tags_csv, priority=pr_val)
    db.add(dbobj)
    db.commit()
    db.refresh(dbobj)
    return schemas.TodoRead.from_orm(dbobj)


@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    obj = db.query(models.Todo).filter(models.Todo.id == todo_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Todo not found")
    db.delete(obj)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.put("/todos/{todo_id}", response_model=schemas.TodoRead)
def update_todo(todo_id: int, todo: schemas.TodoCreate, db: Session = Depends(get_db)):
    obj = db.query(models.Todo).filter(models.Todo.id == todo_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Todo not found")
    obj.title = todo.title
    obj.description = todo.description
    obj.due_date = normalize_due_date(todo.due_date)
    obj.tags = ",".join(todo.tags) if todo.tags else None
    try:
        obj.priority = int(todo.priority) if todo.priority is not None else 0
    except Exception:
        obj.priority = 0
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return schemas.TodoRead.from_orm(obj)

