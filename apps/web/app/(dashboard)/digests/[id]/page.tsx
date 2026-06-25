"use client";

import Link from "next/link";
import { notFound } from "next/navigation";
import { useEffect, useMemo } from "react";
import { ErrorView } from "@/components/common/error-view";
import { ChatFab } from "@/components/chatbot/chat-fab";
import { DigestDetailFooterNav } from "@/components/digest/digest-detail-footer-nav";
import { DigestDetailHero } from "@/components/digest/digest-detail-hero";
import { DigestDetailSkeleton } from "@/components/digest/digest-detail-skeleton";
import { DigestScrollProgress } from "@/components/digest/digest-scroll-progress";
import { DigestSectionCard } from "@/components/digest/digest-section";
import { DigestSummary } from "@/components/digest/digest-summary";
import { DigestToc } from "@/components/digest/digest-toc";
import { sortSections } from "@/lib/digest-detail-utils";
import { resolveDigestIsRead } from "@/lib/digest-read-cache";
import { useAuth } from "@/hooks/use-auth";
import { useDigestDetail } from "@/hooks/use-digest-detail";
import { useDigestReadToggle } from "@/hooks/use-digest-read";
import {
  flattenDigestPages,
  useDigestReadState,
  useDigests,
} from "@/hooks/use-digests";
import { isApiError } from "@/types/api";

interface DigestDetailPageProps {
  params: {
    id: string;
  };
}

export default function DigestDetailPage({ params }: DigestDetailPageProps) {
  const digestId = params.id;
  const { user } = useAuth();
  const { data, isLoading, isError, error, refetch } = useDigestDetail(digestId);
  const listQuery = useDigests({ limit: 50 });
  const markRead = useDigestReadToggle();
  const { data: sessionReadIds } = useDigestReadState();

  const sections = useMemo(
    () => (data ? sortSections(data.sections) : []),
    [data],
  );

  const neighbors = useMemo(() => {
    const items = flattenDigestPages(listQuery.data);
    const index = items.findIndex((item) => item.id === digestId);
    if (index === -1) {
      return { previousId: null, nextId: null };
    }
    return {
      previousId: items[index + 1]?.id ?? null,
      nextId: items[index - 1]?.id ?? null,
    };
  }, [digestId, listQuery.data]);

  useEffect(() => {
    if (!data || !user?.id) return;

    const readIds = sessionReadIds ?? new Set<string>();
    const alreadyRead = resolveDigestIsRead(data, readIds);
    if (!alreadyRead) {
      markRead.mutate({ digestId: data.id, read: true });
    }
  }, [data, markRead, sessionReadIds, user?.id]);

  if (isLoading) {
    return <DigestDetailSkeleton />;
  }

  if (isError) {
    if (isApiError(error) && (error.statusCode === 404 || error.code === "NOT_FOUND")) {
      notFound();
    }

    return (
      <ErrorView
        message={
          isApiError(error)
            ? error.message
            : "Bülten detayı yüklenemedi."
        }
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  if (!data) {
    notFound();
  }

  return (
    <>
      <ChatFab digestId={data.id} />
      <DigestScrollProgress />

      <div className="space-y-6">
        <Link
          href="/digests"
          className="no-print inline-flex items-center text-sm font-semibold text-navy-800 hover:text-gold-500"
        >
          ← Bültenler
        </Link>

        <DigestToc sections={sections} variant="mobile" />

        <div className="grid items-start gap-8 lg:grid-cols-[200px_minmax(0,1fr)]">
          <aside className="digest-print-hide lg:sticky lg:top-6">
            <DigestToc sections={sections} variant="sidebar" />
          </aside>

          <div className="digest-detail-content min-w-0 space-y-6">
            <DigestDetailHero digest={data} />

            <DigestSummary digest={data} />

            <div className="space-y-4">
              {sections.map((section) => (
                <DigestSectionCard key={section.id} section={section} />
              ))}
            </div>

            <DigestDetailFooterNav
              previousId={neighbors.previousId}
              nextId={neighbors.nextId}
            />
          </div>
        </div>
      </div>
    </>
  );
}
