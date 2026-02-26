# LangChain + Langfuse Cluster Validation Test

Deploys a Kubernetes Job that sends prompts to **Gemma3 27B** (via Ollama on the DGX Spark) and traces every call through **Langfuse**. Passing means both the AI workload and the observability stack are working end-to-end.

## Cluster layout discovered

| Component | Endpoint (in-cluster) |
|---|---|
| Ollama (Gemma3 27B) | `ollama.langchain-infra.svc.cluster.local:11434` |
| Langfuse Web UI | `langfuse-web.langfuse.svc.cluster.local:3000` (NodePort 30000) |
| DGX Spark node | `spark-f8d7` (ARM64, `192.168.86.38`) |

## Prerequisites

1. A container registry accessible from your cluster nodes, **or** the ability to build images directly on a node. The instructions below assume building locally and loading into the cluster via `ctr` on a node. Adjust for your registry if you have one.

2. Langfuse API keys — you need to create a project and API key pair in the Langfuse UI first.

## Step-by-step deployment

### 1. Get Langfuse API keys

Open the Langfuse UI in your browser at `http://<any-node-ip>:30000` (e.g. `http://192.168.86.60:30000`).

1. Sign up / log in.
2. Create a new project (e.g. `cluster-test`).
3. Go to **Settings → API Keys** and create a new key pair.
4. Copy the **Public Key** (`pk-lf-...`) and **Secret Key** (`sk-lf-...`).

### 2. Configure secrets

Copy the example and fill in your actual values:

```bash
cp .env.example .env   # if starting fresh, or just edit .env directly
```

Edit `.env` with your keys:

```
LANGFUSE_PUBLIC_KEY=pk-lf-YOUR-ACTUAL-KEY
LANGFUSE_SECRET_KEY=sk-lf-YOUR-ACTUAL-KEY
GITHUB_TOKEN=github_pat_YOUR-ACTUAL-TOKEN
```

> **Note:** `.env` is git-ignored and should never be committed.

### 3. Build the container image

Since the DGX Spark is ARM64 and the other nodes are AMD64, build for the architecture of the node you want the Job to run on. The default Job spec has no node selector, so it will land on any worker. Building for AMD64 (the majority of your nodes):

```bash
cd /Volumes/T9/ai-claude/test-ai-cluster

# Build the image
docker build -t langchain-langfuse-test:latest .
```

> **Note:** If your cluster nodes cannot pull from a registry, you can export and import the image manually:
> ```bash
> docker save langchain-langfuse-test:latest -o /tmp/langchain-langfuse-test.tar
> # Copy to a worker node and import:
> scp /tmp/langchain-langfuse-test.tar user@k8s002:
> ssh user@k8s002 'sudo ctr -n k8s.io images import langchain-langfuse-test.tar'
> ```

### 4. Deploy to Kubernetes

```bash
# Load secrets into the environment
set -a && source .env && set +a

# Create the namespace, secrets (via envsubst), and job
kubectl apply -f k8s/namespace.yaml
envsubst < k8s/secret.yaml | kubectl apply -f -
envsubst < k8s/github-token-secret.yaml | kubectl apply -f -
kubectl apply -f k8s/job.yaml
```

### 5. Watch the test run

```bash
# Watch the pod start
kubectl get pods -n langchain-test -w

# Once the pod is running, stream its logs
kubectl logs -n langchain-test -l app=langchain-langfuse-test -f
```

You should see output like:

```
============================================================
LangChain + Langfuse Cluster Validation Test
============================================================
Ollama URL : http://ollama.langchain-infra.svc.cluster.local:11434
Model      : gemma3:27b
Langfuse   : http://langfuse-web.langfuse.svc.cluster.local:3000

--- Test 1: Simple question ---
Q: What is the capital of France?
A: The capital of France is Paris.
Result: PASS

--- Test 2: Creative prompt ---
Q: Explain why the sky is blue in simple terms.
A: ...
Result: PASS

--- Test 3: Multi-turn conversation ---
Q: What is 7 * 8?
A: 56
Result: PASS

============================================================
Results: 3/3 tests passed
============================================================
ALL TESTS PASSED — cluster validation successful!
```

### 6. Verify in Langfuse

1. Open `http://<any-node-ip>:30000` in your browser.
2. Navigate to your project → **Traces**.
3. You should see traces named `langchain-cluster-test` with spans for each LLM call, including input/output, latency, and token counts.

### 7. Cleanup

```bash
# Delete the job (auto-cleaned after 1 hour via ttlSecondsAfterFinished)
kubectl delete -f k8s/job.yaml

# To remove everything
kubectl delete namespace langchain-test
```

## Re-running the test

Delete the old Job first (Kubernetes won't re-run a completed Job):

```bash
kubectl delete -f k8s/job.yaml
kubectl apply -f k8s/job.yaml
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Pod stuck in `ImagePullBackOff` | Image not on the node. Export/import it or push to a registry. |
| `Connection refused` to Ollama | Verify Ollama is running: `kubectl get endpoints -n langchain-infra ollama` |
| Langfuse traces not appearing | Check the public/secret keys are correct. Check Langfuse worker logs: `kubectl logs -n langfuse -l app.kubernetes.io/component=worker` |
| Pod `OOMKilled` | Increase the memory limit in `k8s/job.yaml` |
| Test hangs on Gemma3 response | The 27B model can take 30-60s per response on first load. Wait. |

## Project structure

```
test-ai-cluster/
├── app/
│   ├── __init__.py
│   └── main.py              # LangChain test script
├── k8s/
│   ├── namespace.yaml        # langchain-test namespace
│   ├── secret.yaml           # Langfuse API credentials
│   └── job.yaml              # Kubernetes Job manifest
├── Dockerfile                # uv-based container build
├── pyproject.toml            # Python dependencies (uv)
└── README.md                 # This file
```
