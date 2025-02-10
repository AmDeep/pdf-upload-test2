from streamlit import set_page_config

test

def set():
    set_page_config(
        page_title="PDF WorkDesk",
        page_icon="📄",
        menu_items={
            "About": f"PDF WorkDesk v{version.__version__}  "
            "\nDeveloper contact: [Siddhant Sadangi](mailto:siddhant.sadangi@gmail.com)",
            "Report a Bug": "https://github.com/SiddhantSadangi/pdf-workdesk/issues/new",
            "Get help": None,
        },
        layout="wide",
    )


if __name__ == "__main__":
    set()
