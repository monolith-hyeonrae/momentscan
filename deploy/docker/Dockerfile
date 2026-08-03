# momentscan 서비스 이미지 — 코드 + 파이썬 스택만 (웨이트 없음).
#
# 3층 분리: 이미지(코드+의존) / 웨이트(S3 번들, entrypoint 전개) / 상태(/data 볼륨).
# CUDA 베이스 불필요 — torch 2.12+cu130 PyPI 휠이 CUDA 유저스페이스를 전부 수반하고,
# 호스트에서는 nvidia-container-toolkit이 드라이버만 패스스루한다 (--gpus all).
#
# 빌드 (레포 루트에서):  docker build -f deploy/docker/Dockerfile -t momentscan:dev .
# 실행: deploy/docker/compose.yaml 참조.

FROM ubuntu:24.04

# ffmpeg=소스 디코드 · libgl1/libglib2.0-0=opencv 런타임 링크 ·
# libgles2/libegl1=mediapipe GLES 요구(없으면 features/parse가 libGLESv2.so.2로 죽는다 — 8/3 실증) ·
# curl=헬스체크·IMDS(스팟 예고) · unzip=AWS CLI 설치용 ·
# build-essential=insightface sdist의 Cython C++ 확장 컴파일 (휠 미제공; 슬리밍은 후속 과제)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 libgles2 libegl1 curl ca-certificates unzip build-essential \
    && rm -rf /var/lib/apt/lists/*

# AWS CLI v2 — entrypoint의 웨이트 번들/캐시 s3 왕복용
RUN curl -sSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip

COPY --from=ghcr.io/astral-sh/uv:0.8.2 /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy
RUN uv python install 3.11

WORKDIR /app

# substrate(visualstack) — 루트 pyproject의 editable 경로 의존(../visualstack/*)이라
# /app의 형제 위치(/visualstack)에 있어야 한다. named build context로 주입:
#   docker build --build-context visualstack=<visualstack 체크아웃 경로> ...
# (compose는 build.additional_contexts가 같은 역할). 코드 트리만 선별 — clips 등 데이터 제외.
COPY --from=visualstack visualbus   /visualstack/visualbus
COPY --from=visualstack visualpath  /visualstack/visualpath
COPY --from=visualstack plugins     /visualstack/plugins

# 의존 레이어 — 락파일과 워크스페이스 멤버 pyproject만으로 서드파티를 먼저 굳힌다.
# 코드 수정이 torch(~2.5GB) 레이어 재빌드로 번지지 않게 하는 캐시 경계.
COPY pyproject.toml uv.lock ./
COPY apps/momentscan/pyproject.toml apps/momentscan/pyproject.toml
COPY plugins/features-specialist45d/pyproject.toml plugins/features-specialist45d/pyproject.toml
COPY plugins/features-vjepa/pyproject.toml plugins/features-vjepa/pyproject.toml
# --all-extras: 서빙 파이프라인이 extra 뒤의 torch 스택을 요구 —
#   step0b(attribute의 depth 플러그인) ⊃ torch+transformers ⊃ backbone(vjepa, 동일 클로저)
# 캐시 마운트: uv 휠 캐시(~10GB)를 레이어 밖으로 — 없으면 이미지가 두 배가 된다
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --all-extras

# 코드 레이어 — .dockerignore가 산출물·웨이트·기록물을 걸러낸다
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-extras

ENV PATH="/app/.venv/bin:${PATH}" \
    HOME=/root \
    # 스팟 콜드부팅에서 HF 원격 HEAD/다운로드 금지 — 웨이트는 번들이 정본
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

ENTRYPOINT ["/app/deploy/docker/entrypoint.sh"]
