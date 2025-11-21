import asyncio
import os
import sys
from google import genai

# Add the current directory to sys.path so we can import app modules
sys.path.append(os.getcwd())

from app.core.config import get_settings
from app.services.gemini_file_search_client import GeminiFileSearchClient

async def main():
    settings = get_settings()
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    store_name = "fileSearchStores/ragtenantfreshdeskdefaultco-q09tf24zcnsr"
    
    if not api_key:
        print("No API Key found.")
        return

    client = genai.Client(api_key=api_key)
    
    print(f"Listing files in store: {store_name}")
    try:
        # List files in the store to inspect their metadata
        # Note: The exact method to list files in a store might vary by SDK version.
        # We will try to iterate over files and check if we can filter by store.
        
        # In the v1beta API, we can list files. 
        # Let's try to list a few and see if they belong to our store.
        count = 0
        for f in client.files.list():
            print(f"\nFile: {f.name} ({f.display_name})")
            # Check if we can see metadata directly
            # Note: The SDK object might not expose metadata directly in the list view
            # We might need to get the file details.
            
            # Try to get file details if possible, or just print what we have
            print(f"  MIME: {f.mime_type}")
            print(f"  State: {f.state}")
            
            # If the file object has metadata/custom_metadata, print it
            if hasattr(f, "metadata"):
                print(f"  Metadata: {f.metadata}")
            
            count += 1
            if count >= 5:
                break
                
    except Exception as e:
        print(f"Error listing files: {e}")

if __name__ == "__main__":
    asyncio.run(main())
