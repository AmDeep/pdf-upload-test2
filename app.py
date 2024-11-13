try:
    import os
    import sys
    import traceback
    from io import BytesIO

    import streamlit as st
    from pypdf import PaperSize, PdfReader, PdfWriter, Transformation
    from pypdf.errors import FileNotDecryptedError
    from streamlit_pdf_viewer import pdf_viewer

    from utils import helpers, init_session_states, page_config

    page_config.set()

    # Initialize session_state variables if they don't exist
    if "file" not in st.session_state:
        st.session_state["file"] = None  # or any default value
    if "name" not in st.session_state:
        st.session_state["name"] = ""  # or any default value
    if "password" not in st.session_state:
        st.session_state["password"] = ""  # or any default value
    if "is_encrypted" not in st.session_state:
        st.session_state["is_encrypted"] = False  # or any default value

    # ---------- HEADER ----------
    st.title("📄 PDF WorkDesk!")
    st.write(
        "User-friendly, lightweight, and open-source tool to preview and extract content and metadata from PDFs, add or remove passwords, modify, merge, convert and compress PDFs."
    )

    init_session_states.init()

    # ---------- OPERATIONS ----------
    try:
        pdf, reader, *other_values = helpers.load_pdf(key="main")

    except FileNotDecryptedError:
        pdf = "password_required"

    if pdf == "password_required":
        st.error("PDF is password protected. Please enter the password to proceed.")
    elif pdf:
        lcol, rcol = st.columns(2)

        with lcol.expander(label="🔍 Extract text"):
            extract_text_lcol, extract_text_rcol = st.columns(2)

            page_numbers_str = helpers.select_pages(
                container=extract_text_lcol,
                key="extract_text_pages",
            )

            mode = extract_text_rcol.radio(
                "Extraction mode",
                options=["plain", "layout"],
                horizontal=True,
                help="Layout mode extracts text in a format resembling the layout of the source PDF",
            )

            if page_numbers_str:
                try:
                    text = helpers.extract_text(reader, page_numbers_str, mode)
                except (IndexError, ValueError):
                    st.error("Specified pages don't exist. Check the format.", icon="⚠️")
                else:
                    st.text(text)

                    with open("text.txt", "w", encoding="utf-8") as f:
                        f.write(text)

                    with open("text.txt") as f:
                        st.download_button(
                            "💾 Download extracted text",
                            data=f,
                            use_container_width=True,
                        )

        with rcol.expander(label="️🖼️ Extract images"):
            if page_numbers_str := helpers.select_pages(
                container=st,
                key="extract_image_pages",
            ):
                try:
                    images = helpers.extract_images(reader, page_numbers_str)
                except (IndexError, ValueError):
                    st.error("Specified pages don't exist. Check the format.", icon="⚠️")
                else:
                    if images:
                        for data, name in images.items():
                            st.image(data, caption=name)
                    else:
                        st.info("No images found")

        with lcol.expander("📊 Extract table"):
            if page_numbers_str := helpers.select_pages(
                container=st,
                key="extract_table_pages",
            ):
                helpers.extract_tables(
                    st.session_state["file"],  # Use session_state["file"]
                    page_numbers_str,
                )

        with rcol.expander("🔄️ Convert to Word"):
            st.caption("Takes ~1 second/page. Will remove password if present")

            if st.button("Convert PDF to Word", use_container_width=True):
                st.download_button(
                    "📥 Download Word document",
                    data=helpers.convert_pdf_to_word(pdf),
                    file_name=f"{st.session_state['name'][:-4]}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        # Removed password-related operations here

        with lcol.expander("🔃 Rotate PDF"):
            # TODO: Add password back to converted PDF if original was protected
            st.caption("Will remove password if present")
            angle = st.slider(
                "Clockwise angle",
                min_value=0,
                max_value=270,
                step=90,
                format="%d°",
            )

            with PdfWriter() as writer:
                for page in reader.pages:
                    writer.add_page(page)
                    writer.pages[-1].rotate(angle)

                # TODO: Write to byte_stream
                writer.write("rotated.pdf")

                with open("rotated.pdf", "rb") as f:
                    pdf_viewer(f.read(), height=250, width=300)
                    st.download_button(
                        "📥 Download rotated PDF",
                        data=f,
                        mime="application/pdf",
                        file_name=f"{st.session_state['name'].rsplit('.')[0]}_rotated_{angle}.pdf",
                        use_container_width=True,
                    )

        # Further operations...

except Exception as e:
    st.error(
        f"""The app has encountered an error:  
        `{e}`  
        Please create an issue [here](https://github.com/SiddhantSadangi/pdf-workdesk/issues/new) 
        with the below traceback""",
        icon="🥺",
    )
    st.code(traceback.format_exc())

st.success(
    "[Star the repo](https://github.com/SiddhantSadangi/pdf-workdesk) to show your :heart:",
    icon="⭐",
)
