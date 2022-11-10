deploy index using
```bash
gcloud datastore indexes create index.yaml
```

deploy function using
```bash
gcloud functions deploy indents-backend \
--gen2 \
--region=europe-west2 \
--runtime=python310 \
--source=. \
--entry-point=db_call \
--trigger-http \
--allow-unauthenticated \
--memory=128MiB \
--serve-all-traffic-latest-revision \
--timeout=10s \
--max-instances=1
```

retrieve url
```bash
gcloud functions describe indents-backend \
--gen2 \
--region=europe-west2 \
--format="value(serviceConfig.uri)"
```
