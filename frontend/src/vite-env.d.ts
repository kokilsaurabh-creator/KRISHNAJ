/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "pdfmake/build/pdfmake" {
  const pdfMake: {
    vfs: unknown;
    createPdf: (doc: unknown) => {
      download: (filename?: string) => void;
      open: () => void;
      getBlob: (cb: (blob: Blob) => void) => void;
      getBase64: (cb: (data: string) => void) => void;
    };
  };
  export default pdfMake;
}

declare module "pdfmake/build/vfs_fonts";
