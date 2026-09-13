# clinic-booking Kubernetes manifests

Kustomize base + overlays. `base/` holds everything shared between
environments; `overlays/dev` and `overlays/prod` layer on environment-specific
config, secrets, and patches.

## Dev (minikube)

One-time cluster setup:

```sh
minikube start
minikube addons disable ingress   # traefik and the default ingress addon can't both bind :80/:443
minikube addons enable traefik
echo "$(minikube ip) clinic-booking.local" | sudo tee -a /etc/hosts
```

Build the image straight into minikube's own Docker daemon (so
`imagePullPolicy: Never` in the dev overlay can find it without a registry):

```sh
eval $(minikube docker-env)
docker build -t clinic-booking-app:latest .
```

Deploy:

```sh
kubectl apply -k k8s/overlays/dev
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=db -n clinic-booking --timeout=120s
kubectl apply -f k8s/base/migrate-job.yaml   # already applied via the overlay, but re-apply to force a run
```

Jobs are immutable once created — to re-run migrations after a schema
change, delete and reapply:

```sh
kubectl delete job clinic-migrate -n clinic-booking
kubectl apply -k k8s/overlays/dev
```

Visit `https://clinic-booking.local` (accept the self-signed cert warning) or
`http://clinic-booking.local`.

## Prod

Before applying, replace every `REPLACE_WITH_*` / `REPLACE_ME_*` placeholder
in `overlays/prod/` — registry path and tag, domain, ACME email, cloud
StorageClass name, and real secret values (see the warning comment in
`overlays/prod/kustomization.yaml` about not committing real secrets as
plain literals).

```sh
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
kubectl create secret docker-registry registry-credentials \
  --docker-server=... --docker-username=... --docker-password=... -n clinic-booking
kubectl apply -k k8s/overlays/prod
kubectl delete job clinic-migrate -n clinic-booking   # after the first deploy, before every subsequent one
kubectl apply -k k8s/overlays/prod
```

## Notes

- **StorageClass**: `base/db/statefulset.yaml` deliberately leaves
  `storageClassName` unset, so it uses whatever's marked default —
  minikube's default is `standard`. `overlays/prod` patches in an explicit
  cloud StorageClass; run `kubectl get storageclass` on your target cluster
  to see what's available.
- **NetworkPolicy**: enforced only if your CNI supports it. minikube's
  default network plugin doesn't — start with `--cni=calico` to test it
  locally.
- **DATABASE_URL**: differs from the value you gave for local (non-Docker)
  development. Inside the cluster the app reaches Postgres via the
  Service DNS name (`db.clinic-booking.svc.cluster.local`), not `localhost`.
