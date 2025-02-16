from typing import List, Callable, Optional
import traceback
import os
from datetime import datetime
import httpx
import aiofiles
import mimetypes
from urllib.parse import urlparse
import pandas as pd

from agentic.common import RunContext
from agentic.tools.registry import tool_registry


@tool_registry.register(
    name="RAG Tool for knowledge retrievel",
    description="Searches for content [RAG] in knowledge indexes.",
    dependencies=[
        tool_registry.Dependency(
            name="textract",
            type="pip",
            version="https://github.com/supercog-ai/textract.git",
        ),
        tool_registry.Dependency(
            name="pypdf2",
            type="pip",
            version="^3.0.1",
        ),
        tool_registry.Dependency(
            name="html2text",
            type="pip",
            version="^2020.1.16",
        ),
    ]
)
class RAGTool:
    def get_tools(self) -> List[Callable]:
        return [
            self.list_documents,
            self.search_knowledge_index,
            self.search_document_summaries,
            self.review_full_document,
        ]


    # async def save_content_to_knowledge_index(self, content_or_url: str, index_name: str, annotation: Optional[str] = None) -> str:
    #     """Saves content to the specified knowledge index. This should only be used on urls and large text blocks.
    #         If a message has a file attached to it like `uploaded file: <file_name>` do not use this function.
    #         The content should be either text or a URL to a website. The indedex name should be the name of the
    #         currently enabled index. An optional annotation can provide context about the content."""
    #     from ..celery_app import app
    #     from ..celery_tasks import process_single_document_async

    #     mime_type = "text/plain"
    #     source_url = None
    #     if content_or_url.startswith("http"):
    #         source_url = content_or_url
    #         result, mime_type = await RAGTool._universal_read_file(content_or_url, self.run_context)
    #         if isinstance(result, pd.DataFrame):
    #             # Render dataframe to CSV content
    #             content_or_url = result.to_csv(index=False)
    #         else:
    #             content_or_url = result

    #     with app.connection_for_write() as conn:
    #         try:
    #             index: DocIndexReference|None = self.run_context.find_doc_index_by_name(index_name)
    #             if index is None:
    #                 avail = ",".join([i.name for i in self.run_context.get_doc_indexes()])
    #                 return f"Index {index_name} not found. Available indexes: {avail}."

    #             # Get a file name for the document
    #             extension = mimetypes.guess_extension(mime_type)
    #             OPENAI_API_KEY = config.get_global("OPENAI_API_KEY", required=False)
    #             if OPENAI_API_KEY is None:
    #                 file_name = f"chat_{datetime.now().strftime('%Y%m%d%H%M%S')}{extension}"
    #             else:
    #                 # Use OpenAI to generate a file name base on the content of the file
    #                 client = OpenAI(api_key=OPENAI_API_KEY)

    #                 system_prompt = """
    #                 You are a helpful assistant that generates a file name for a document based on its content.
    #                 The file name should be a short, descriptive name that includes the document's main topic or subject.
    #                 The file name should be concise and easy to understand.
    #                 The file name should not include any special characters or punctuation marks.
    #                 The file name should not indlude spaces, use underscores instead.
    #                 The file name should not include the file extension.
    #                 Return only the file name, no other text.
    #                 """
    #                 response = client.chat.completions.create(
    #                     model="gpt-4-turbo-preview",
    #                     messages=[
    #                         {
    #                             "role": "system",
    #                             "content": system_prompt,
    #                         },
    #                         {
    #                             "role": "user",
    #                             "content": f"Generate a file name for the following document:\n\n{content_or_url[:10000]}",
    #                         },
    #                     ],
    #                     temperature=0.5,
    #                     max_tokens=100,
    #                 )
    #                 file_name = response.choices[0].message.content.strip()
    #                 print(f"Generated file name: {file_name}")
                
    #             # Upload to s3 if it was not a url
    #             if source_url is None:
    #                 with open(file_name, "w") as f:
    #                     f.write(content_or_url)

    #                 upload_result = self.run_context.upload_user_file_to_s3(file_name=file_name, mime_type=mime_type)
    #                 if "url" in upload_result:
    #                     source_url = upload_result["url"]

    #             process_single_document_async.apply_async(
    #                 args=[],
    #                 kwargs={
    #                     "tenant_id": self.run_context.tenant_id,
    #                     "index_id": index.index_id,
    #                     "file_name": file_name,
    #                     "content": content_or_url,
    #                     "source_url": source_url,
    #                     "owner": self.run_context.get_current_user_name() or self.run_context.get_current_user_email(),
    #                     "content_type": mime_type,
    #                     "annotation": annotation  # Pass through the annotation
    #                 },
    #                 connection=conn
    #             )
                
    #             return f"Content is being saved to index {index_name}. This may take a few minutes."
    #         except Exception as e:
    #             traceback.print_exc()
    #             return f"Error saving text: {str(e)}"

    @staticmethod
    async def _universal_read_file(
            file_name: str, 
            run_context: RunContext,
            mime_type: str|None=None
        ) -> tuple[str|pd.DataFrame, str]:
        import html2text
        import textract
        from PyPDF2 import PdfReader

        if file_name.startswith("http"):
            # Read from URL
            dwn_file, mime_type = await RAGTool._download_url_as_file(file_name)
            if dwn_file.startswith("Error:"):
                return dwn_file

            return await RAGTool._universal_read_file(dwn_file, run_context, mime_type)

        if not os.path.exists(file_name):
            raise ValueError(f"File {file_name} not found.")
        
        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(file_name, False)

        if mime_type is None:
            raise ValueError("Error - unable to determine the file type")
        elif mime_type.startswith("image/"):
            raise ValueError("Enable the Image Analysis & Recognition tool to read image files.")
        
        try:
            if mime_type == "text/csv":
                return pd.read_csv(file_name), mime_type
            
            elif mime_type in ["text/plain", "application/json", "application/xml"] or mime_type.startswith("text/"):
                return open(file_name, 'r').read(), mime_type
        
            elif 'html' in mime_type:
                # Use beautifulsoup to extract text
                return html2text.html2text(open(file_name).read()), mime_type
            
            elif mime_type == "application/pdf":
                pdf_reader = PdfReader(open(file_name, "rb"))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                
                return text, mime_type

            elif mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                return pd.read_excel(file_name, sheet_name=0, engine='openpyxl'), mime_type
            else:
                return textract.process(file_name), mime_type

        except Exception as e:

            print(f"Error reading file {file_name}: {e}. Fall back to textract.")
            return textract.process(file_name)


    @staticmethod
    async def _download_url_as_file(url: str, file_name_hint: str="") -> [str,str]:
        # Returns the saved file name, and the original URL mime type
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            print(r)
            save_file = file_name_hint or RAGTool.get_last_path_component(url)

            if r.status_code == 200:
                mime_type = r.headers.get('content-type', '').split(';')[0]

                async with aiofiles.open(save_file, 'wb') as f:
                    async for chunk in r.aiter_bytes(chunk_size=8192):
                        if chunk:
                            await f.write(chunk)
                return save_file, mime_type 
            else:
                raise ValueError(f"Error: {r.status_code} {r.text}")

    @staticmethod
    def get_last_path_component(url: str) -> str:
        # Parse the URL
        parsed_url = urlparse(url)
        # Get the path from the parsed URL
        path = parsed_url.path
        # Split the path and get the last component
        last_component = path.split('/')[-1]
        if not last_component.strip():
            last_component = "_".join(path.strip('/').split('/'))
            if not last_component:
                last_component = parsed_url.hostname or "download"

        return last_component

    def list_documents(
            self, 
            index_name: str,
            page: int = 1,
            page_size: int = 10
        ) -> str:
        """List documents in the specified index.
        
        Args:
            index_name: The name of the index to list documents from. Use your enabled index.
            page: Page number (default: 1)
            page_size: Number of documents per page (default: 10)
            
        Returns:
            List of documents in the index formatted as a markdown table
        """
        try:
            index = self.run_context.get_default_index(index_name)
            if index is None:
                avail = ",".join([i.name for i in self.run_context.get_doc_indexes()])
                return f"Index {index_name} not found. Available indexes: {avail}."
            
            index_id = index.id
            index_files, total_count = txtai_get_index_files(
                index_id,
                page,
                page_size
            )

            result = f"Documents in {index_name} (Page {page}, showing {len(index_files)} of {total_count}):\n\n"
            result += "| Document Name | Created | Owner | ID |\n"
            result += "|---------------|---------|--------|----|\n"
            
            for file in index_files:
                result += f"| {file['name']} | {file['created_at']} | {file['owner']} | {file['id']} |\n"

            return LLMFullResult(result)

        except Exception as e:
            return f"Error listing documents: {str(e)}"

    def search_knowledge_index(
            self, 
            index_name: str = None,
            threshold: float = 0,
            query: str = None,
            search_type: str = "content"
        ) -> dict:
        """Search for documents relevant to the query. Searches all indices by default. Provide threshold to determine
            how relevant the search results should be."""
        try:
            index = self.run_context.get_default_index(index_name)
            if index is None:
                avail = ",".join([i.name for i in self.run_context.get_doc_indexes()])
                return f"Index {index_name} not found. Available indexes: {avail}."
            
            results = []
            with unrestricted_filesystem():
                if query:
                    results = txtai_search_index(
                        index_id=index.id, 
                        tenant_id=self.run_context.tenant_id, 
                        query=query,
                        search_type=search_type
                    )
                else:
                    files_list, _ = txtai_get_index_files(index.id, 1, 10)
                    results = files_list
            
            results = [{ 
                **result, 
                "source_url": get_accessible_url(result["source_url"]),
                "text": f"{result['text']}\n\nSource: {result.get('citation', 'Unknown source')}" if result.get('citation') else result['text']
            } for result in results]

            df = pd.DataFrame(results)
            
            columns = ['score', 'text', 'citation', 'document_name', 'type', 'source_url', 'summary']
            df = df[sorted(set(columns) & set(df.columns))]
            
            return self.get_dataframe_preview(df, max_rows=10)

        except Exception as e:
            traceback.print_exc()
            return f"Error searching documents: {str(e)}"

    def search_document_summaries(
            self,
            query: str,
            index_name: str = None,
            threshold: float = 0
        ) -> dict:
        """
        Search specifically in document summaries, then perform a hybrid search within the most relevant document.
        This helps find the most relevant document by topic, then locates the most relevant chunks within it.
        
        This function uses a two-stage search:
        1. First searches document summaries to identify the single most relevant document
        2. Then performs a detailed search within that document's chunks to find specific information
        
        Use this function when the user wants focused information from a single authoritative document.
        Use search_knowledge_index() instead for broad searches - it searches across all document chunks
        simultaneously and returns matches from multiple documents.
        """
        try:
            index = self.run_context.get_default_index(index_name)
            if index is None:
                avail = ",".join([i.name for i in self.run_context.get_doc_indexes()])
                return f"Index {index_name} not found. Available indexes: {avail}."

            # First find the most relevant document by summary
            with unrestricted_filesystem():
                summary_results = txtai_search_index(
                    index_id=index.id, 
                    tenant_id=self.run_context.tenant_id, 
                    query=query,
                    search_type="summary"
                )

            if not summary_results:
                return "No relevant documents found"

            # Get the most relevant document's ID
            most_relevant_doc = max(summary_results, key=lambda x: x["score"])
            doc_id = most_relevant_doc["doc_id"]
            
            # Now search within that document's chunks
            with unrestricted_filesystem():
                chunk_results = txtai_hybrid_search(
                    index_id=index.id,
                    tenant_id=self.run_context.tenant_id,
                    query=query,
                    doc_id=doc_id
                )

            results = [{ 
                **result, 
                "source_url": get_accessible_url(result["source_url"]),
                "text": f"{result['text']}\n\nSource: {result.get('citation', 'Unknown source')}" if result.get('citation') else result['text']
            } for result in chunk_results]
            
            df = pd.DataFrame(results)
            
            columns = ['score', 'text', 'citation', 'document_name', 'type', 'source_url']
            df = df[sorted(set(columns) & set(df.columns))]
            
            return self.get_dataframe_preview(df, max_rows=10)

        except Exception as e:
            traceback.print_exc()
            return f"Error in hybrid document search: {str(e)}"

    async def review_full_document(self, index_name: str, query: str, doc_id: Optional[str] = None):
        """
        Use this function when a user asks to review a full or whole document. You should use this
        instead of knowledge_index_search when a user asks questions about a full document.
        Adds a full document to the context of the current run using a query to search for the relevant document.
        Must provide a query to search for the relevant document or a document id.

        Args:
            index_name: The name of the index to search for the relevant document
            query: [Optional The query to search for the relevant document
            doc_id: [Optional] The ID of the document to add to the context
        """
        try:
            index = self.run_context.get_default_index(index_name)
            if index is None:
                avail = ",".join([i.name for i in self.run_context.get_doc_indexes()])
                return f"Index {index_name} not found. Available indexes: {avail}."
            
            index_id = index.id
            if doc_id is None:
                with unrestricted_filesystem():
                    results = txtai_search_index(
                        index_id=index_id,
                        tenant_id=self.run_context.tenant_id,
                        query=query
                    )
                if len(results) == 0:
                    return "No documents found."
                
                doc_id = results[0]["doc_id"]
            
            metadata, chunks = txtai_get_chunks_for_document(index_id=index_id, doc_id=doc_id)
            
            await self.run_context.publish(
                self.run_context.create_event(
                    AddDocumentToContextEvent,
                    callbacks=callbacks,
                    doc_id=doc_id,
                    metadata=metadata,
                    chunks=chunks
                )
            )
            return f"Added document '{metadata.get('name', 'Unknown')}' to context with {len(chunks)} chunks"
        except Exception as e:
            traceback.print_exc()
            return f"Error adding full document to context: {str(e)}"
