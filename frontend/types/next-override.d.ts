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

  export interface Viewport {
    themeColor?: string | string[];
    colorScheme?: string;
    width?: string;
    initialScale?: number;
    maximumScale?: number;
    minimumScale?: number;
    userScalable?: boolean;
  }

  export interface MetadataRoute {
    Robots: {
      rules: {
        userAgent?: string | string[];
        allow?: string | string[];
        disallow?: string | string[];
        crawlDelay?: number;
      } | Array<{
        userAgent: string | string[];
        allow?: string | string[];
        disallow?: string | string[];
        crawlDelay?: number;
      }>;
      sitemap?: string | string[];
      host?: string;
    };
    Sitemap: Array<{
      url: string;
      lastModified?: string | Date;
      changeFrequency?: 'always' | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'yearly' | 'never';
      priority?: number;
      alternates?: {
        languages?: Record<string, string>;
      };
    }>;
    Manifest: {
      name?: string;
      short_name?: string;
      description?: string;
      start_url?: string;
      display?: string;
      background_color?: string;
      theme_color?: string;
      icons?: Array<{
        src: string;
        sizes?: string;
        type?: string;
        purpose?: string;
      }>;
    };
  }
}

declare module "next/navigation" {
  export function usePathname(): string;
  export function useRouter(): {
    push: (url: string) => void;
    replace: (url: string) => void;
    prefetch: (url: string) => void;
    back: () => void;
    forward: () => void;
    refresh: () => void;
  };
  export function useSearchParams(): URLSearchParams;
  export function redirect(url: string): never;
  export function notFound(): never;
}

declare module "next/link" {
  import { ReactNode } from "react";
  export default function Link({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
    [key: string]: any;
  }): JSX.Element;
}