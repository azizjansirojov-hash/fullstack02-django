/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DJANGO_ORIGIN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
