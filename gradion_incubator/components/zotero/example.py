from dotenv import load_dotenv

from gradion_incubator.components.zotero.api import load_group_library


def main():
    lib = load_group_library()
    # lib.sync()

    root = lib.root()
    root.print()

    for collection in root.sub_collections():
        print(collection)

    for document in root.sub_documents():
        if "arxiv.org" in document.url:
            arxiv_id = document.url.split("/")[-1][:10]
            print(arxiv_id)


if __name__ == "__main__":
    load_dotenv()
    main()
