declare module "next" {
  export interface Metadata {
    title?: string | { default: string; template: string };
    description?: string;
    metadataBase?: URL;
    applicationName?: string;
    generator?: string;
    referrer?: string;
    keywords?: string[] | string;
    authors?: { name: string; url?: string }[] | { name: string; url?: string };
    creator?: string;
    publisher?: string;
    formatDetection?: string | { email: boolean; address: boolean; telephone: boolean };
    robots?: string | { index?: boolean; follow?: boolean; googleBot?: string };
    openGraph?: {
      title?: string;
      description?: string;
      url?: string;
      siteName?: string;
      type?: string;
      locale?: string;
      images?: { url: string; width?: number; height?: number; alt?: string }[];
    };
    twitter?: {
      card?: string;
      site?: string;
      creator?: string;
      title?: string;
      description?: string;
      images?: string[];
    };
    verification?: {
      google?: string;
      yandex?: string;
      ykey?: string;
      me?: string[];
    };
    other?: Record<string, string>;
  }
}