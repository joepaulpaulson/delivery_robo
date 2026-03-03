from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import google.generativeai as genai

class MedicalAgent:
    def __init__(self, api_key):
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
        # Load your local medical knowledge base (CSV/PDFs of symptoms)
        self.vector_db = FAISS.load_local("medical_db", self.embeddings)
        
    def get_diagnosis_context(self, user_query):
        # Retrieve top 3 relevant medical facts
        docs = self.vector_db.similarity_search(user_query, k=3)
        return "\n".join([d.page_content for d in docs])

    def generate_safe_response(self, user_input):
        context = self.get_diagnosis_context(user_input)
        
        prompt = f"""
        SYSTEM: You are a professional medical triage agent. 
        CONTEXT FROM MEDICAL DATABASE: {context}
        
        USER SYMPTOMS: {user_input}
        
        INSTRUCTIONS:
        1. Base your suggestions ONLY on the provided Context.
        2. If symptoms match 'Emergency' criteria (chest pain, stroke signs), 
           MANDATE calling emergency services immediately.
        3. Never say "You have [disease]". Say "Your symptoms are consistent with [possibility]".
        4. Suggest the appropriate specialist (e.g., Neurologist).
        """
        model = genai.GenerativeModel("gemini-1.5-pro")
        return model.generate_content(prompt).text