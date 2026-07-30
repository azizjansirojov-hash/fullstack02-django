/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DJANGO_ORIGIN?: string
  readonly VITE_REACT_READER_ENABLED?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
