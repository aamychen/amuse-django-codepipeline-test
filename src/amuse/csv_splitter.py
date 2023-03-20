import csv
import io

from django.core.files.uploadedfile import InMemoryUploadedFile


class CsvSplitter:
    @classmethod
    def split_csv_stream(
        cls, in_stream: io.IOBase, output_row_limit: int
    ) -> io.StringIO:
        in_stream.seek(0)
        reader = csv.reader(in_stream)
        headers = next(reader)

        out_writer = None
        total_rows = 0
        for i, row in enumerate(reader):
            total_rows += 1
            is_new_chunk = (i % output_row_limit) == 0 or i == 0
            if is_new_chunk:
                out_stream = io.StringIO()
                out_writer = csv.writer(out_stream)
                out_writer.writerow(*[headers])
            out_writer.writerow(*[row])

            is_next_row_new_chunk = (i + 1) % output_row_limit == 0
            if is_next_row_new_chunk:
                out_stream.seek(0)
                yield out_stream

        is_already_yielded = total_rows % output_row_limit == 0
        if not is_already_yielded:
            out_stream.seek(0)
            yield out_stream

    @classmethod
    def split_uploaded_file(
        cls, csv_in: InMemoryUploadedFile, output_row_limit: int
    ) -> io.StringIO:
        return cls.split_csv_stream(
            io.StringIO(csv_in.read().decode('utf-8')), output_row_limit
        )
