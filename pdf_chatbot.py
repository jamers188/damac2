import os
import streamlit as st
import hashlib
from PyPDF2 import PdfReader
import openai

# Page configuration
st.set_page_config(
    page_title="Simple PDF Chatbot",
    page_icon="📚",
    layout="wide",
)

# Ensure data directories exist
os.makedirs("pdf_files", exist_ok=True)

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

if "pdf_content" not in st.session_state:
    st.session_state.pdf_content = {}

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
            pdfs[name] = {
                "path": os.path.join("pdf_files", filename),
                "processed": name in st.session_state.pdf_content
            }
    return pdfs

def process_pdf(pdf_name, pdf_path):
    """Process a PDF file by extracting its text."""
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_path)
        
        if not text:
            return False, "Could not extract text from PDF. Make sure it contains selectable text."
        
        # Store the PDF content in session state
        st.session_state.pdf_content[pdf_name] = text
        
        return True, "PDF processed successfully."
    except Exception as e:
        return False, f"Error processing PDF: {str(e)}"

def chat_with_pdf(question, pdf_content):
    """Chat with a PDF using OpenAI API."""
    try:
        # Setup OpenAI client
        openai.api_key = st.session_state.openai_api_key
        
        # Create the prompt
        prompt = f"""
        I have a PDF document with the following content:
        
        {pdf_content[:4000]}  # Limit content to avoid token issues
        
        Based only on the information above, please answer the following question:
        {question}
        
        If the answer is not in the provided content, please respond with: "I don't see information about that in the document."
        """
        
        # Call the OpenAI API
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers questions based only on the provided PDF content."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        # Return the response
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating response: {str(e)}"

# Main app views
def main_view():
    """Display the main view with options to go to admin or user view."""
    st.title("📚 Simple PDF Chatbot")
    
    st.write("""
    Welcome to the Simple PDF Chatbot! This application allows you to chat with your PDF documents.
    
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
                               help="Extracts text for chat functionality")
            
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
                                
                                # Remove from session state if processed
                                if name in st.session_state.pdf_content:
                                    del st.session_state.pdf_content[name]
                                
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
            
            # Update current PDF
            if selected_pdf != st.session_state.current_pdf:
                st.session_state.current_pdf = selected_pdf
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
    elif not st.session_state.current_pdf:
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
                    pdf_content = st.session_state.pdf_content.get(st.session_state.current_pdf, "")
                    response = chat_with_pdf(user_question, pdf_content)
                    st.write(response)
                    
                    # Add assistant message to chat history
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
        
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
