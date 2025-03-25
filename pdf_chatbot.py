import os
import streamlit as st
import pickle
import hashlib
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.vectorstores.faiss import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain

# Page configuration
st.set_page_config(
    page_title="PDF Chatbot",
    page_icon="📚",
    layout="wide",
)

# Ensure data directories exist
os.makedirs("pdf_files", exist_ok=True)
os.makedirs("vectorstores", exist_ok=True)

# Password for admin panel (SHA-256 hash)
ADMIN_PASSWORD_HASH = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"  # "admin"

# Initialize session states
if "view" not in st.session_state:
    st.session_state.view = "main"  # main, admin, user

if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ""

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "current_pdf" not in st.session_state:
    st.session_state.current_pdf = None

if "conversation" not in st.session_state:
    st.session_state.conversation = None

# Utility functions
def hash_password(password):
    """Create a SHA-256 hash of a password."""
    return hashlib.sha256(password.encode()).hexdigest()

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    pdf_reader = PdfReader(pdf_path)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def get_pdf_files():
    """Get list of available PDF files."""
    pdfs = {}
    for filename in os.listdir("pdf_files"):
        if filename.endswith(".pdf"):
            name = filename[:-4]  # Remove .pdf extension
            vector_path = os.path.join("vectorstores", f"{name}.pkl")
            pdfs[name] = {
                "path": os.path.join("pdf_files", filename),
                "processed": os.path.exists(vector_path),
                "vector_path": vector_path
            }
    return pdfs

def process_pdf(pdf_name, pdf_path):
    """Process a PDF file and create embeddings."""
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    
    # Split text into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    chunks = text_splitter.split_text(text)
    
    if not chunks:
        return False, "Could not extract text from PDF. Make sure it contains selectable text."
    
    try:
        # Create embeddings and vector store
        embeddings = OpenAIEmbeddings(api_key=st.session_state.openai_api_key)
        vectorstore = FAISS.from_texts(chunks, embeddings)
        
        # Save vector store
        vector_path = os.path.join("vectorstores", f"{pdf_name}.pkl")
        with open(vector_path, "wb") as f:
            pickle.dump(vectorstore, f)
        
        return True, "PDF processed successfully."
    except Exception as e:
        return False, f"Error processing PDF: {str(e)}"

def setup_conversation(vector_path):
    """Set up the conversation chain."""
    try:
        # Load vector store
        with open(vector_path, "rb") as f:
            vectorstore = pickle.load(f)
        
        # Create LLM
        llm = ChatOpenAI(
            temperature=0.2,
            model="gpt-3.5-turbo",
            api_key=st.session_state.openai_api_key
        )
        
        # Create memory
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Create chain
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
            memory=memory
        )
        
        return chain
    except Exception as e:
        st.error(f"Error setting up conversation: {str(e)}")
        return None

# Main app views
def main_view():
    """Display the main view with options to go to admin or user view."""
    st.title("📚 PDF Chatbot")
    
    st.write("""
    Welcome to the PDF Chatbot! This application allows you to chat with your PDF documents.
    
    ### Choose an option:
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔐 Admin Panel", use_container_width=True):
            st.session_state.view = "admin_login"
            st.experimental_rerun()
    
    with col2:
        if st.button("💬 User Chat", use_container_width=True):
            st.session_state.view = "user"
            st.experimental_rerun()
    
    st.markdown("""
    ### How It Works
    
    1. **Admin**: Upload and process PDF documents
    2. **User**: Select a processed document and ask questions about it
    3. **AI**: Get instant answers based on the content of your documents
    
    This chatbot uses OpenAI's language models to analyze your PDFs and answer questions.
    You'll need an OpenAI API key to use this application.
    """)

def admin_login_view():
    """Display the admin login view."""
    st.title("🔐 Admin Login")
    
    password = st.text_input("Enter admin password:", type="password", 
                           help="Default password is 'admin'")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Login"):
            if hash_password(password) == ADMIN_PASSWORD_HASH:
                st.session_state.view = "admin"
                st.experimental_rerun()
            else:
                st.error("Incorrect password. Please try again.")
    
    with col2:
        if st.button("Back to Main"):
            st.session_state.view = "main"
            st.experimental_rerun()

def admin_view():
    """Display the admin panel."""
    st.title("🔐 Admin Panel")
    
    # Sidebar for API key
    with st.sidebar:
        st.title("Settings")
        
        api_key = st.text_input(
            "OpenAI API Key:", 
            type="password",
            value=st.session_state.openai_api_key
        )
        
        if api_key:
            st.session_state.openai_api_key = api_key
            st.success("✅ API key set")
        else:
            st.warning("⚠️ API key required")
        
        if st.button("Logout"):
            st.session_state.view = "main"
            st.experimental_rerun()
    
    # Main admin panel with tabs
    tab1, tab2 = st.tabs(["Upload PDF", "Manage PDFs"])
    
    # Tab 1: Upload PDF
    with tab1:
        st.header("Upload New PDF")
        
        with st.form("upload_form"):
            pdf_file = st.file_uploader("Upload PDF file:", type="pdf")
            pdf_name = st.text_input("PDF Name (optional):", 
                                   help="Leave blank to use filename")
            process = st.checkbox("Process PDF after upload", value=True,
                               help="Creates embeddings for chat functionality")
            
            submit = st.form_submit_button("Upload PDF")
            
            if submit:
                if not pdf_file:
                    st.error("Please upload a PDF file.")
                else:
                    # Prepare filename
                    if not pdf_name:
                        pdf_name = pdf_file.name.replace(".pdf", "")
                    
                    # Clean filename
                    pdf_name = pdf_name.replace(" ", "_").lower()
                    
                    # Save PDF file
                    pdf_path = os.path.join("pdf_files", f"{pdf_name}.pdf")
                    with open(pdf_path, "wb") as f:
                        f.write(pdf_file.getbuffer())
                    
                    st.success(f"PDF '{pdf_name}' uploaded successfully!")
                    
                    # Process PDF if requested
                    if process:
                        if not st.session_state.openai_api_key:
                            st.error("OpenAI API key is required to process PDFs.")
                        else:
                            with st.spinner("Processing PDF... This may take a while."):
                                success, message = process_pdf(pdf_name, pdf_path)
                                if success:
                                    st.success(message)
                                else:
                                    st.error(message)
    
    # Tab 2: Manage PDFs
    with tab2:
        st.header("Manage PDFs")
        
        pdfs = get_pdf_files()
        if not pdfs:
            st.info("No PDFs uploaded yet. Go to 'Upload PDF' to add documents.")
        else:
            for name, info in pdfs.items():
                with st.expander(f"📄 {name}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Show status
                        if info["processed"]:
                            st.success("Status: Processed ✅")
                        else:
                            st.warning("Status: Not processed ⚠️")
                            
                            # Process button
                            if st.button(f"Process now", key=f"process_{name}"):
                                if not st.session_state.openai_api_key:
                                    st.error("OpenAI API key is required.")
                                else:
                                    with st.spinner(f"Processing {name}..."):
                                        success, message = process_pdf(name, info["path"])
                                        if success:
                                            st.success(message)
                                            st.experimental_rerun()
                                        else:
                                            st.error(message)
                    
                    with col2:
                        # Delete button
                        if st.button(f"Delete PDF", key=f"delete_{name}"):
                            try:
                                # Delete PDF file
                                if os.path.exists(info["path"]):
                                    os.remove(info["path"])
                                
                                # Delete vector store if exists
                                if os.path.exists(info["vector_path"]):
                                    os.remove(info["vector_path"])
                                
                                st.success(f"PDF '{name}' deleted successfully.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Error deleting PDF: {str(e)}")

def user_view():
    """Display the user chat interface."""
    st.title("💬 PDF Chatbot")
    
    # Sidebar for settings
    with st.sidebar:
        st.title("Settings")
        
        # API key input
        api_key = st.text_input(
            "OpenAI API Key:", 
            type="password",
            value=st.session_state.openai_api_key
        )
        
        if api_key:
            st.session_state.openai_api_key = api_key
            st.success("✅ API key set")
        else:
            st.warning("⚠️ API key required")
        
        st.divider()
        
        # Get all PDFs
        pdfs = get_pdf_files()
        processed_pdfs = {name: info for name, info in pdfs.items() if info["processed"]}
        
        if not processed_pdfs:
            st.warning("No processed PDFs available. Ask an administrator to upload and process documents.")
        else:
            # PDF selection
            pdf_names = list(processed_pdfs.keys())
            current_index = 0
            if st.session_state.current_pdf in pdf_names:
                current_index = pdf_names.index(st.session_state.current_pdf)
                
            selected_pdf = st.selectbox(
                "Select PDF:",
                options=pdf_names,
                index=current_index
            )
            
            # Initialize conversation when PDF changes
            if selected_pdf != st.session_state.current_pdf:
                if not st.session_state.openai_api_key:
                    st.error("Please provide an OpenAI API key.")
                else:
                    with st.spinner("Loading document..."):
                        st.session_state.current_pdf = selected_pdf
                        st.session_state.conversation = setup_conversation(
                            processed_pdfs[selected_pdf]["vector_path"]
                        )
                        st.session_state.chat_history = []
        
        # Back button
        if st.button("Back to Main"):
            st.session_state.view = "main"
            st.experimental_rerun()
    
    # Main chat area
    if not st.session_state.openai_api_key:
        st.warning("Please enter your OpenAI API key in the sidebar to start chatting.")
    elif not processed_pdfs:
        st.warning("No processed PDFs available. Ask an administrator to upload and process documents.")
    elif not st.session_state.conversation:
        st.info("Select a PDF from the sidebar to start chatting.")
    else:
        # Display chat messages
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Chat input
        user_question = st.chat_input("Ask a question about your PDF...")
        
        if user_question:
            # Add user message to chat history
            st.session_state.chat_history.append({"role": "user", "content": user_question})
            
            # Display user message
            with st.chat_message("user"):
                st.write(user_question)
            
            # Generate and display response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = st.session_state.conversation.run(user_question)
                        st.write(response)
                        
                        # Add assistant message to chat history
                        st.session_state.chat_history.append({"role": "assistant", "content": response})
                    except Exception as e:
                        st.error(f"Error generating response: {str(e)}")
        
        # Reset chat button
        if st.session_state.chat_history and st.button("Clear Chat"):
            st.session_state.chat_history = []
            st.experimental_rerun()

# Main app
def main():
    # Determine which view to display
    if st.session_state.view == "main":
        main_view()
    elif st.session_state.view == "admin_login":
        admin_login_view()
    elif st.session_state.view == "admin":
        admin_view()
    elif st.session_state.view == "user":
        user_view()

if __name__ == "__main__":
    main()
