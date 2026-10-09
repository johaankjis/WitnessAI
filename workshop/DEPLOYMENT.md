# Team 6 transfer, preflight, deployment and rollback

No deployment is performed by TASK-005C or by `release.py`. Run Mac steps locally;
all `kubectl`, credentials, VSS readiness and real evidence checks below are VM-only.
The workshop's `deployment/deploy-app-no-registry` implementation is not present in
this repository. This procedure updates an **existing** compatible Team 6 app using
its current image, Service and Ingress. It does not invent a private platform CLI.
If there is no existing app, provision it using the VM's official workshop deployment
instructions first. Stop if its shape fails preflight; do not silently replace it.

ConfigMaps are limited to 1 MiB; our serialized source cap is 750,000 bytes. Source
is flat, and runtime dependencies belong in the existing image, not the ConfigMap.
Versioned immutable ConfigMaps prevent rollback from referring to overwritten code.
References: [Kubernetes ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
and [Deployments/rollback](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).

## 1. Build and transfer from Mac

```sh
workshop/.venv/bin/python -m pytest workshop/tests -q
python3 workshop/release.py preflight
python3 workshop/release.py package --output /tmp/witness-workshop.tar
cd /tmp
shasum -a 256 -c witness-workshop.tar.sha256
# TEAM6_VM is your SSH alias from the workshop operator; never commit its endpoint.
scp witness-workshop.tar witness-workshop.tar.sha256 "$TEAM6_VM:~/"
```

The archive contains only allowlisted source/docs/tests, plus a per-file manifest.
Review `tar -tf /tmp/witness-workshop.tar` before transfer. Never transfer the repo,
`.env`, a virtualenv, videos, or signed URLs.

## 2. Inspect and prepare on the VM (bash)

Use the Team 6 kube context supplied by the workshop operator. These are placeholders
for **resource names from that context**, not private endpoints:

```bash
set -euo pipefail
umask 077
cd "$HOME"
sha256sum -c witness-workshop.tar.sha256
RELEASE_DIR=$(mktemp -d "$HOME/witness-release.XXXXXX")
tar -xf ~/witness-workshop.tar -C "$RELEASE_DIR"
cd "$RELEASE_DIR/witness-workshop"
python3 release.py verify
kubectl config current-context
kubectl -n team-6 get deployment,service,ingress
read -r -p 'Existing app Deployment name: ' APP_DEPLOYMENT
read -r -p 'Existing app Service name: ' APP_SERVICE
read -r -p 'Existing app Ingress name: ' APP_INGRESS
kubectl -n team-6 get deployment "$APP_DEPLOYMENT" -o json > before-deployment.json
kubectl -n team-6 get service "$APP_SERVICE" -o json > service.json
kubectl -n team-6 get ingress "$APP_INGRESS" -o json > ingress.json
# Inspect these VM-local files to identify the app container and source volume.
read -r -p 'App container name: ' APP_CONTAINER
read -r -p 'Source ConfigMap volume name: ' APP_VOLUME
```

Keep `before-deployment.json` protected on the VM: existing deployments may contain
sensitive environment values. Record its current source ConfigMap name and rollout
revision (`kubectl -n team-6 rollout history deployment/"$APP_DEPLOYMENT"`). Keep the
old ConfigMap and ReplicaSets for rollback. Do not upload these files to Git.

The existing image must already have Python 3.11+, FastAPI, uvicorn, requests, and
compatible Pydantic. Verify without calling VSS:

```bash
kubectl -n team-6 exec deployment/"$APP_DEPLOYMENT" -c "$APP_CONTAINER" -- python -c \
'import sys, fastapi, uvicorn, requests, pydantic; assert sys.version_info >= (3,11); print(sys.version); print(fastapi.__version__, uvicorn.__version__, requests.__version__, pydantic.__version__)'
```

Compare versions with `requirements.txt`. If dependencies are missing or incompatible,
stop and use the workshop's approved image/dependency provisioning workflow. This
release does not install packages into a read-only source mount or select a new image.

## 3. VM configuration and offline preflight

Use an existing Kubernetes Secret with keys `VSS_URL`, `VSS_USERNAME`, `VSS_PASSWORD`,
or create one from a protected VM-local env file provided by the team operator. Do
not use literal credentials in CLI arguments or commit the file. Example creation:

```bash
read -r -p 'Protected VM VSS env file path: ' VSS_ENV_FILE
read -r -p 'Secret name for this release: ' VSS_SECRET
kubectl -n team-6 create secret generic "$VSS_SECRET" --from-env-file="$VSS_ENV_FILE"
# The file must contain plain KEY=value lines (not shell code).
# Enter the same values for syntax-only preflight; read -s avoids terminal echo.
read -r -s -p 'VSS URL: ' VSS_URL; printf '\n'
read -r -s -p 'VSS username: ' VSS_USERNAME; printf '\n'
read -r -s -p 'VSS password: ' VSS_PASSWORD; printf '\n'
export VSS_URL VSS_USERNAME VSS_PASSWORD
export WITNESS_WORKSHOP_MODE=vast
python3 release.py preflight --vm --deployment before-deployment.json \
  --service service.json --ingress ingress.json --container "$APP_CONTAINER" \
  --volume "$APP_VOLUME" --secret "$VSS_SECRET" --output plan
unset VSS_URL VSS_USERNAME VSS_PASSWORD
```

For an already-existing Secret, skip creation and set `VSS_SECRET` to its name.
Verify its key names on the VM without printing values:

```bash
kubectl -n team-6 get secret "$VSS_SECRET" -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}'
```

Preflight checks source size, env syntax, namespace, whole-directory ConfigMap mount,
Service selectors/port 8080, and `/app` Ingress routing. It emits `plan/configmap.json`
and `plan/deployment.json`; it never applies them. Inspect the diff against the old
Deployment: only source volume, app command/working directory and required env should
change. Preserve existing image, selectors, resources, probes and other platform settings.
The app handles `/app` whether the ingress strips that prefix or preserves it.

## 4. Operator-authorized deployment only

```bash
kubectl apply --dry-run=server -f plan/configmap.json
kubectl apply --dry-run=server -f plan/deployment.json
# After review and deployment authorization:
kubectl apply -f plan/configmap.json
kubectl apply -f plan/deployment.json
kubectl -n team-6 rollout status deployment/"$APP_DEPLOYMENT" --timeout=120s
```

Use the workshop portal's Team 6 **App** tab. Verify assets, `/app/health` reports
`mode=vast` and `synthetic=false`, all six reviews show the correct source and 25–30s
window, optional scoped Q&A remains advisory, and video seeks with Range/206 work.
A health response alone does not validate VSS connectivity. These VSS calls must be
made only on the VM/approved workshop network. Do not copy responses or signed links
into the repo. If authentication, compatibility, footage, or provenance checks fail,
stop the demonstration and roll back; never switch a real demo silently to fixtures.

## 5. Rollback

Record the prior rollout revision before step 4. With that exact number:

```bash
read -r -p 'Recorded previous deployment revision: ' PREVIOUS_REVISION
kubectl -n team-6 rollout undo deployment/"$APP_DEPLOYMENT" --to-revision="$PREVIOUS_REVISION"
kubectl -n team-6 rollout status deployment/"$APP_DEPLOYMENT" --timeout=120s
```

This restores the previous pod template, including its previous ConfigMap/Secret
references and command. Retaining those objects is mandatory. If rollout history was
pruned, restore the saved deployment specification using the operator's approved
restore process with `before-deployment.json`; do not overwrite a newer concurrent
release. Recheck the App tab and health. Keep failed release artifacts VM-local for
inspection. Do not delete prior ConfigMaps/Secrets until rollback retention ends.
