import type { Metadata, Viewport } from "next";
import "react-image-crop/dist/ReactCrop.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Photo Shadow Art — STLジェネレーター",
  description:
    "写真を線幅で濃淡を表現するシャドウアート風の3DプリントSTLに変換するツール",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
