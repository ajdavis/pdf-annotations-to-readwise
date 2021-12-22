import fitz
doc = fitz.open('/Users/emptysquare/Dropbox/Research Papers/Research 1/Consensus and Replication 1/PODC 2021 Design and Verification of a Logless Dynamic Reconfiguration Protocol in MongoDB Replication/PODC 2021 Design and Verification of a Logless Dynamic Reconfiguration Protocol in MongoDB Replication ANNOTATED.pdf')
page = doc[1]
print(page)
print(list(page.annots()))
print()
for a in list(page.annots(types=[fitz.PDF_ANNOT_FREE_TEXT])):
    print(a.info['content'])
    print()

for a in list(page.annots(types=[fitz.PDF_ANNOT_UNDERLINE])):
    # Experimentally determined offset to get text associated with an underline.
    # TODO: try expanding the rect in increments until text is non-empty.
    rect = fitz.Rect(
        a.rect.x0 - 1,
        a.rect.y0 - 7,
        a.rect.x1 + 1,
        a.rect.y1 + 3
    )
    print(f'"{page.get_textbox(rect)}"')
    print(a.info)
    print()
