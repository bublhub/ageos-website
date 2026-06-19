const LATEST_RELEASE_API = "https://api.github.com/repos/ageos-labs/ageos-runtime/releases/latest";
const LATEST_RELEASE_PAGE = "https://github.com/ageos-labs/ageos-runtime/releases/latest";

const DOWNLOADS = {
  linux: {
    extension: ".deb",
    label: "Linux",
  },
  windows: {
    extension: ".exe",
    label: "Windows",
  },
};

export async function onRequest(context) {
  const target = getDownloadTarget(context.params.path);

  if (!target) {
    if (typeof context.next === "function") {
      return context.next();
    }

    return context.env.ASSETS.fetch(context.request);
  }

  try {
    const release = await fetchLatestRelease();
    const asset = findAsset(release.assets, target.extension);

    if (!asset?.browser_download_url) {
      return redirect(LATEST_RELEASE_PAGE);
    }

    return redirect(asset.browser_download_url);
  } catch {
    return redirect(LATEST_RELEASE_PAGE);
  }
}

function getDownloadTarget(pathParam) {
  const path = Array.isArray(pathParam) ? pathParam.join("/") : pathParam || "";
  const firstSegment = path.split("/")[0].toLowerCase();

  if (firstSegment.startsWith("linux")) {
    return DOWNLOADS.linux;
  }

  if (firstSegment.startsWith("windows")) {
    return DOWNLOADS.windows;
  }

  return null;
}

async function fetchLatestRelease() {
  const response = await fetch(LATEST_RELEASE_API, {
    headers: {
      Accept: "application/vnd.github+json",
      "User-Agent": "ageos-website",
    },
    cf: {
      cacheTtl: 300,
      cacheEverything: true,
    },
  });

  if (!response.ok) {
    throw new Error(`GitHub release lookup failed: ${response.status}`);
  }

  return response.json();
}

function findAsset(assets = [], extension) {
  const candidates = assets.filter((asset) => asset.name?.toLowerCase().endsWith(extension));

  return (
    candidates.find((asset) => asset.name.toLowerCase().includes("x64")) ||
    candidates.find((asset) => asset.name.toLowerCase().includes("amd64")) ||
    candidates[0]
  );
}

function redirect(location) {
  return new Response(null, {
    status: 302,
    headers: {
      "Cache-Control": "public, max-age=300",
      Location: location,
    },
  });
}
