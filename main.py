import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from bson import ObjectId

# Database helpers
from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
# Models
# -------------------------------
class ConversationCreate(BaseModel):
    title: str = Field(..., min_length=1)
    model: str = Field("gpt-4o-mini")

class ConversationOut(BaseModel):
    id: str
    title: str
    model: str

class MessageCreate(BaseModel):
    role: Literal["user", "system"] = "user"
    content: str = Field(..., min_length=1)

class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str


# -------------------------------
# Helpers
# -------------------------------

def to_str_id(doc):
    if not doc:
        return doc
    d = dict(doc)
    if d.get("_id"):
        d["id"] = str(d.pop("_id"))
    return d


def simple_ai_response(user_text: str) -> str:
    """Very simple placeholder AI response to avoid external API keys.
    This simulates an assistant like Kiwi AI.
    """
    user_text = user_text.strip()
    # Provide a helpful, structured response
    tips = (
        "Aqui está um rascunho de resposta e próximos passos:\n\n"
        "Resumo: " + (user_text[:180] + ("..." if len(user_text) > 180 else "")) + "\n\n"
        "Sugestões:\n"
        "- Se precisar, posso gerar um plano passo a passo.\n"
        "- Posso criar listas, tabelas em Markdown e exemplos de código.\n"
        "- Diga 'refinar' para melhorar alguma parte específica.\n\n"
        "Ferramentas mentais usadas: decomposição, exemplos, checklist."
    )
    return f"Entendi. {tips}"


# -------------------------------
# Routes
# -------------------------------
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Conversations
@app.post("/api/conversations", response_model=ConversationOut)
def create_conversation(payload: ConversationCreate):
    data = payload.model_dump()
    conv_id = create_document("conversation", data)
    return {"id": conv_id, **data}


@app.get("/api/conversations", response_model=List[ConversationOut])
def list_conversations():
    docs = get_documents("conversation", {})
    out: List[ConversationOut] = []
    for d in docs:
        out.append(ConversationOut(id=str(d.get("_id")), title=d.get("title"), model=d.get("model", "gpt-4o-mini")))
    # Sort by creation (ObjectId time) desc
    out.sort(key=lambda x: ObjectId(x.id).generation_time, reverse=True)
    return out


@app.get("/api/conversations/{conversation_id}/messages", response_model=List[MessageOut])
def list_messages(conversation_id: str):
    try:
        ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation id")
    docs = get_documents("message", {"conversation_id": conversation_id})
    msgs: List[MessageOut] = []
    for d in docs:
        msgs.append(MessageOut(id=str(d.get("_id")), role=d.get("role"), content=d.get("content")))
    return msgs


@app.post("/api/conversations/{conversation_id}/messages", response_model=List[MessageOut])
def send_message(conversation_id: str, payload: MessageCreate):
    """Stores the user message and a generated assistant reply. Returns the two messages."""
    try:
        ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation id")

    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Create user message
    user_msg = {
        "conversation_id": conversation_id,
        "role": payload.role,
        "content": payload.content,
    }
    user_id = create_document("message", user_msg)

    # Generate assistant reply (placeholder AI)
    reply_text = simple_ai_response(payload.content)
    assistant_msg = {
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": reply_text,
    }
    asst_id = create_document("message", assistant_msg)

    return [
        MessageOut(id=user_id, role=user_msg["role"], content=user_msg["content"]),
        MessageOut(id=asst_id, role="assistant", content=reply_text),
    ]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
