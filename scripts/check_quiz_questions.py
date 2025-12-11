import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client, ClientOptions

# Load from .env.local explicitly
load_dotenv(".env.local")

SUPABASE_URL = os.getenv("SUPABASE_COMMON_URL")
SUPABASE_KEY = os.getenv("SUPABASE_COMMON_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials not found in environment variables.")
    exit(1)

# Use 'onboarding' schema
supabase = create_client(SUPABASE_URL, SUPABASE_KEY, options=ClientOptions(schema="onboarding"))

async def main():
    print(f"Connecting to {SUPABASE_URL[:20]} with schema 'onboarding'...")
    
    # Try curriculum_modules
    try:
        print("Fetching modules from 'curriculum_modules'...")
        response = supabase.table("curriculum_modules").select("id, name_ko, slug").execute()
        table_name = "curriculum_modules"
    except Exception as e:
        print(f"Failed to fetch from 'curriculum_modules': {e}")
        return

    print(f"Successfully connected to '{table_name}'")
    
    target_module_id = None
    for module in response.data:
        print(f"ID: {module['id']}, Name: {module['name_ko']}, Slug: {module['slug']}")
        if "Freshsales" in module['name_ko'] and "Omni" in module['name_ko']:
            target_module_id = module['id']
            
    if target_module_id:
        print(f"\nFound target module ID: {target_module_id}")
        
        print("\nFetching questions for this module...")
        q_response = supabase.table("quiz_questions").select("id, question, module_id").eq("module_id", target_module_id).execute()
        
        for q in q_response.data:
            print(f"Question ID: {q['id']}")
            print(f"Question: {q['question']}")
            print("-" * 20)
            
            if "온보딩 과정의 주요 목표" in q['question'] or "회사 정책" in q['question'] or "입사 초기" in q['question']:
                print("!!! FOUND INCORRECT QUESTION !!!")
                print(f"Deleting question {q['id']}...")
                supabase.table("quiz_questions").delete().eq("id", q['id']).execute()
                print("Deleted.")

if __name__ == "__main__":
    asyncio.run(main())
