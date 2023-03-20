from io import BytesIO

import pytest
from django.core.files.uploadedfile import InMemoryUploadedFile

from amuse.csv_splitter import CsvSplitter


@pytest.fixture()
def csv_headers():
    return 'name,amount,id'


@pytest.fixture()
def csv_rows():
    return [
        'bugs bunny,10,id1',
        'daffy duck,20,id2',
        'lola,30,id3',
        'speedy gonzales,40,id4',
        'yosemite sam,50,id5',
    ]


@pytest.fixture()
def csv_uploaded_file_mock(csv_headers, csv_rows):
    rows = '\n'.join(csv_rows)
    csv = '\n'.join([csv_headers, rows])
    return InMemoryUploadedFile(
        BytesIO(str.encode(csv, 'utf-8')),
        None,
        'file.csv',
        'text/csv',
        len(csv),
        None,
        None,
    )


@pytest.mark.parametrize(
    'rows_per_chunk,expected_chunks',
    [(200, 1), (6, 1), (5, 1), (4, 2), (3, 2), (2, 3), (1, 5)],
)
def test_csv_splitter(
    rows_per_chunk, expected_chunks, csv_uploaded_file_mock, csv_headers, csv_rows
):
    out_streams = list(
        CsvSplitter.split_uploaded_file(csv_uploaded_file_mock, rows_per_chunk)
    )

    # test chunks count
    assert len(out_streams) == expected_chunks

    # test content
    for chunk_index, stream in enumerate(out_streams):
        start_row_index = rows_per_chunk * chunk_index
        for row_index, value in enumerate(stream):
            # remove newline character
            row = value.rstrip()
            if row_index == 0:
                assert csv_headers == row
                continue

            assert csv_rows[start_row_index + row_index - 1] == row
