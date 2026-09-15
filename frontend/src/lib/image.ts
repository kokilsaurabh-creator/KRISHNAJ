/** Client-side downscale before upload.
 *
 * A phone photo is 3-5 MB, and nobody needs that to read a UPI reference
 * or a cheque number. Resizing to 1200px on the long edge takes it to a
 * few hundred KB, which is cheaper to store, far quicker to upload on a
 * shop's connection, and quicker to load back on the payment screen.
 * The server still enforces its own size and type limits.
 */

const MAX_EDGE = 1200;
const JPEG_QUALITY = 0.82;

export async function resizeImage(file: File): Promise<File> {
  const bitmap = await createImageBitmap(file);
  const { width, height } = bitmap;
  const scale = Math.min(1, MAX_EDGE / Math.max(width, height));

  // Already small enough, and re-encoding would only lose quality.
  if (scale === 1 && file.type === "image/jpeg") {
    bitmap.close();
    return file;
  }

  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);

  const context = canvas.getContext("2d");
  if (!context) {
    bitmap.close();
    return file;
  }
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
  );
  if (!blob) return file;

  const name = file.name.replace(/\.[^.]+$/, "") || "photo";
  return new File([blob], `${name}.jpg`, { type: "image/jpeg" });
}
