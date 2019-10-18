FROM python:3.7

ADD gh_labeler.py /gh_labeler.py
ADD requirements.txt /requirements.txt

RUN pip install -r requirements.txt
RUN chmod +x gh_labeler.py
ENTRYPOINT ["/gh_labeler.py"]
