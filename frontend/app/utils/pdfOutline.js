export async function resolvePdfOutlinePage(pdfDocument, destination) {
  const resolvedDestination =
    typeof destination === "string"
      ? await pdfDocument.getDestination(destination)
      : destination;
  const pageReference = resolvedDestination?.[0];

  if (pageReference == null) return null;

  if (Number.isInteger(pageReference)) {
    return pageReference + 1;
  }

  return (await pdfDocument.getPageIndex(pageReference)) + 1;
}

export async function normalizePdfOutline(
  pdfDocument,
  outlineItems = [],
  parentPath = [],
) {
  return Promise.all(
    outlineItems.map(async (item, index) => {
      const path = [...parentPath, index];
      let page = null;

      if (item.dest != null) {
        try {
          page = await resolvePdfOutlinePage(pdfDocument, item.dest);
        } catch (error) {
          console.warn(`Could not resolve PDF outline item "${item.title || ""}"`, error);
        }
      }

      return {
        id: path.join("."),
        title: item.title?.trim() || "Untitled section",
        page,
        children: await normalizePdfOutline(
          pdfDocument,
          item.items || [],
          path,
        ),
      };
    }),
  );
}

export function flattenPdfOutline(items = [], depth = 0, flattened = []) {
  for (const item of items) {
    flattened.push({ ...item, depth });
    flattenPdfOutline(item.children || [], depth + 1, flattened);
  }
  return flattened;
}

export function findActivePdfOutlineItem(items, currentPage) {
  const page = Number(currentPage);
  if (!Number.isFinite(page)) return null;

  let active = null;
  for (const item of flattenPdfOutline(items)) {
    if (!Number.isInteger(item.page) || item.page > page) continue;
    if (
      !active ||
      item.page > active.page ||
      (item.page === active.page && item.depth > active.depth)
    ) {
      active = item;
    }
  }
  return active;
}

export function findPdfOutlinePath(items = [], targetId, path = []) {
  for (const item of items) {
    const nextPath = [...path, item.id];
    if (item.id === targetId) return nextPath;
    const childPath = findPdfOutlinePath(item.children || [], targetId, nextPath);
    if (childPath) return childPath;
  }
  return null;
}

export function getExpandablePdfOutlineIds(items = [], ids = []) {
  for (const item of items) {
    if (item.children?.length) ids.push(item.id);
    getExpandablePdfOutlineIds(item.children || [], ids);
  }
  return ids;
}
