# K3S/Kubernetes Deployment

These manifests replace the ingestor `docker-compose.yml` with Kubernetes resources for K3S.

## Components

- `timescaledb.yaml`: TimescaleDB `StatefulSet`, internal `Service`, and PVC.
- `ingestor.yaml`: Ingestor `Deployment`, OPC UA certificate PVC, and `settings.json`/`TagList.csv` mounts.
- `configmap.yaml`: Non-secret environment variables.
- `../kustomization.yaml`: Generates the `kepserverlogger-files` `ConfigMap` and rewrites image names/tags for the private registry.
- `secret.example.yaml`: Credentials template. It does not contain real values.

## Prepare Credentials

Create the namespace and the secret with the real values:

```sh
kubectl apply -f k8s/namespace.yaml
kubectl create secret generic kepserverlogger-secret \
  -n kepserverlogger \
  --from-literal=DB_USER='postgres' \
  --from-literal=DB_PASSWORD='REPLACE_ME' \
  --from-literal=KEPSERVER_USERNAME='REPLACE_ME' \
  --from-literal=KEPSERVER_PASSWORD='REPLACE_ME'
```

## Configure Runtime Files

Kustomize generates the `kepserverlogger-files` `ConfigMap` from the real files at the repository root:

- `settings.json`
- `TagList.csv`

`TagList.csv` is treated as a local deployment input. Make sure it exists at the repository root before running `kubectl apply -k .`.

Edit those files directly when the runtime configuration or tag list changes. Then apply from the repository root:

```sh
kubectl apply -k .
kubectl -n kepserverlogger rollout status deployment/ingestor
```

Kustomize adds a hash to the generated `ConfigMap` name. When `settings.json` or `TagList.csv` changes, the hash changes and the ingestor `Deployment` rolls out with the new files.

Non-secret variables live in `kepserverlogger-env`; credentials must live in the `Secret`.

## Ingestor Image

This deployment expects images to be pulled from a private registry. The image names and tags are configured in `../kustomization.yaml`:

```yaml
images:
  - name: ingestors
    newName: registry.local/kepserverlogger/ingestors
    newTag: 0.1.0
  - name: timescale/timescaledb
    newName: registry.local/kepserverlogger/timescaledb
    newTag: latest-pg16
```

Update `registry.local`, repository names, and tags for the target environment.

Build and push the ingestor image:

```sh
docker build -f ingestors/Dockerfile -t registry.local/kepserverlogger/ingestors:0.1.0 .
docker push registry.local/kepserverlogger/ingestors:0.1.0
```

Mirror the TimescaleDB image if the cluster should not pull from Docker Hub:

```sh
docker pull timescale/timescaledb:latest-pg16
docker tag timescale/timescaledb:latest-pg16 registry.local/kepserverlogger/timescaledb:latest-pg16
docker push registry.local/kepserverlogger/timescaledb:latest-pg16
```

Create the registry pull secret in the cluster:

```sh
kubectl create secret docker-registry kepserverlogger-registry \
  -n kepserverlogger \
  --docker-server=registry.local \
  --docker-username='REPLACE_ME' \
  --docker-password='REPLACE_ME' \
  --docker-email='REPLACE_ME'
```

The ingestor `Deployment` and TimescaleDB `StatefulSet` reference this secret through `imagePullSecrets`.

If the registry does not require authentication, remove `imagePullSecrets` from `k8s/ingestor.yaml` and `k8s/timescaledb.yaml`.

For an air-gapped K3S cluster without a registry, the alternative is to load the image on each node that may run the pod:

```sh
./build_ingestor.sh ingestors/Dockerfile ingestors
sudo k3s ctr images import ingestors.tar.gz
```

That manual import path is simpler for a single node, but a private registry is easier to operate across multiple nodes and releases.

## Deploy

```sh
kubectl apply -k .
kubectl -n kepserverlogger rollout status statefulset/timescaledb
kubectl -n kepserverlogger rollout status deployment/ingestor
```

## Operations

View logs:

```sh
kubectl -n kepserverlogger logs deploy/ingestor -f
```

Temporarily access TimescaleDB from the administration machine:

```sh
kubectl -n kepserverlogger port-forward svc/timescaledb 5432:5432
```

The ingestor OPC UA certificate is generated in the `ingestor-certs` PVC. After the first startup, trust that certificate in KepServer the same way the Docker `ingestors-certs` volume was handled.

## OPC UA Networking Note

The ingestor only initiates outbound connections to KepServer (`KEPSERVER_SERVER_URL`). In K3S, it usually does not need `hostNetwork`. If the KepServer firewall filters by IP and only allows the node IP, verify that pod egress traffic leaves through that IP or enable `hostNetwork: true` in the Deployment `PodSpec`.
