from fastapi import APIRouter, Depends, HTTPException, status
import os
import google.generativeai as genai
from supabase import create_client, Client

from app.schemas.user import UserResponse
from app.auth import get_current_user
from app.config import settings
from pydantic import BaseModel

router = APIRouter()

class DoubtRequest(BaseModel):
    query: str
    topic_context: str = ""

def get_supabase() -> Client:
    # get supabase envs
    url = getattr(settings, "SUPABASE_URL", os.getenv("SUPABASE_URL"))
    key = getattr(settings, "SUPABASE_KEY", os.getenv("SUPABASE_KEY"))
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase configuration missing.")
    return create_client(url, key)

@router.get("/history")
def get_chat_history(current_user: UserResponse = Depends(get_current_user)):
    try:
        supabase = get_supabase()
        res = supabase.table('chat_history').select('history').eq('user_id', str(current_user.id)).execute()
        if res.data and len(res.data) > 0:
            return {"history": res.data[0]['history']}
        return {"history": []}
    except Exception as e:
        # fallback to empty history
        print(f"Supabase GET Error: {e}")
        return {"history": []}

@router.post("/solve")
def solve_doubt(
    request: DoubtRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_api_key_here":
            return {"answer": f"Simulated AI Tutor Response for: '{request.query}'. (Please configure a valid GEMINI_API_KEY)."}

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # connect supabase to get history
        supabase = get_supabase()
        user_id_str = str(current_user.id)
        res = supabase.table('chat_history').select('history').eq('user_id', user_id_str).execute()
        
        chat_history = []
        if res.data and len(res.data) > 0:
            chat_history = res.data[0]['history']

        # if first message, insert context
        question = request.query
        if request.topic_context and len(chat_history) == 0:
            question = f"Context: {request.topic_context}\n\nQuestion: {question}"

        # start chat with loaded history
        chat = model.start_chat(history=chat_history)
        
        if len(chat_history) == 0:
            instruction = "You are a helpful engineering tutor focused on SSC JE Civil Engineering. Answer clearly and concisely.\n\n"
            response = chat.send_message(instruction + question)
        else:
            response = chat.send_message(question)

        # build updated history arrays which tracks the session
        updated_history = []
        for msg in chat.history:
            updated_history.append({
                "role": msg.role,
                "parts": [part.text for part in msg.parts]
            })

        # save back to Supabase
        supabase.table('chat_history').upsert({
            'user_id': user_id_str,
            'history': updated_history
        }).execute()

        return {"answer": response.text}

    except Exception as e:
        print(f"AI/DB Service Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI/DB Service Error: {str(e)}")
