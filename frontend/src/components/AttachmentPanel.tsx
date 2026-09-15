import { IconCamera, IconPhoto, IconTrash, IconX } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError, api, type Attachment } from "../lib/api";
import { resizeImage } from "../lib/image";
import { useOnlineStatus } from "../lib/useOnlineStatus";

export default function AttachmentPanel({
  entityType,
  entityId,
  label = "Photos",
  hint,
}: {
  entityType: string;
  entityId: number;
  label?: string;
  hint?: string;
}) {
  const { can } = useAuth();
  const online = useOnlineStatus();
  const queryClient = useQueryClient();
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const [viewing, setViewing] = useState<Attachment | null>(null);
  const [error, setError] = useState<string | null>(null);

  const queryKey = ["attachments", entityType, entityId];
  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () =>
      api.get<Attachment[]>(`/attachments?entity_type=${entityType}&entity_id=${entityId}`),
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const resized = await resizeImage(file);
      const form = new FormData();
      form.append("entity_type", entityType);
      form.append("entity_id", String(entityId));
      form.append("file", resized, resized.name);
      return api.postMultipart<Attachment>("/attachments", form);
    },
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not upload that image."),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/attachments/${id}`),
    onSuccess: () => {
      setViewing(null);
      void queryClient.invalidateQueries({ queryKey });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not remove that image."),
  });

  function onPicked(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Cleared so picking the same file twice in a row still fires change.
    event.target.value = "";
    if (file) upload.mutate(file);
  }

  const attachments = data ?? [];
  const canDelete = can("delete_attachments");
  const busy = upload.isPending || !online;

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-medium text-neutral-700">{label}</h3>
        {hint && <p className="text-xs text-neutral-500">{hint}</p>}
      </div>

      {/* Two separate inputs: `capture` opens the camera straight away,
          without it Android and iOS offer the photo library. */}
      <input
        ref={cameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={onPicked}
      />
      <input ref={galleryRef} type="file" accept="image/*" className="hidden" onChange={onPicked} />

      <div className="flex flex-wrap gap-3">
        {isLoading && <p className="text-sm text-neutral-500">Loading…</p>}

        {attachments.map((attachment) => (
          <button
            key={attachment.id}
            type="button"
            onClick={() => setViewing(attachment)}
            className="h-20 w-20 overflow-hidden rounded-lg border border-neutral-200 transition hover:border-teal"
          >
            <img src={attachment.url} alt={attachment.filename} className="h-full w-full object-cover" />
          </button>
        ))}

        {upload.isPending && (
          <div className="flex h-20 w-20 items-center justify-center rounded-lg border border-dashed border-neutral-300 text-xs text-neutral-500">
            Uploading…
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="btn-secondary gap-2 px-3 text-sm"
          disabled={busy}
          onClick={() => cameraRef.current?.click()}
        >
          <IconCamera size={18} stroke={1.75} />
          Take photo
        </button>
        <button
          type="button"
          className="btn-secondary gap-2 px-3 text-sm"
          disabled={busy}
          onClick={() => galleryRef.current?.click()}
        >
          <IconPhoto size={18} stroke={1.75} />
          Choose file
        </button>
      </div>

      {error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {viewing && (
        <div
          className="fixed inset-0 z-40 flex flex-col bg-black/90"
          role="dialog"
          aria-modal="true"
          aria-label={viewing.filename}
        >
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            {canDelete ? (
              <button
                type="button"
                onClick={() => remove.mutate(viewing.id)}
                disabled={remove.isPending || !online}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-white/85 transition hover:bg-white/10 disabled:opacity-50"
              >
                <IconTrash size={18} stroke={1.75} />
                {remove.isPending ? "Removing…" : "Remove"}
              </button>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={() => setViewing(null)}
              aria-label="Close"
              className="rounded-lg p-2 text-white/85 transition hover:bg-white/10"
            >
              <IconX size={20} />
            </button>
          </div>
          <button
            type="button"
            className="flex flex-1 items-center justify-center p-4"
            onClick={() => setViewing(null)}
            aria-label="Close"
          >
            <img src={viewing.url} alt={viewing.filename} className="max-h-full max-w-full object-contain" />
          </button>
        </div>
      )}
    </section>
  );
}
