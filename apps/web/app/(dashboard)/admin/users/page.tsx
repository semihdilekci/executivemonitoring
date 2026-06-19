"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RoleGate } from "@/components/auth/role-gate";
import { UserFormModal } from "@/components/admin/user-form-modal";
import { UserTable } from "@/components/admin/user-table";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorView } from "@/components/common/error-view";
import { UserTableSkeleton } from "@/components/common/loading-skeleton";
import { Toast } from "@/components/common/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  flattenUserPages,
  useCreateUser,
  useInitiatePasswordReset,
  useUpdateUser,
  useUsers,
} from "@/hooks/use-users";
import { useAuth } from "@/hooks/use-auth";
import type { UserListItem } from "@/types/api";
import type { UserRole } from "@/types/models";
import { isApiError } from "@/types/api";

type RoleFilter = "all" | UserRole;
type StatusFilter = "all" | "active" | "inactive";

interface ToastState {
  message: string;
  variant: "success" | "error";
}

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();

  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingUser, setEditingUser] = useState<UserListItem | null>(null);
  const [toggleTarget, setToggleTarget] = useState<UserListItem | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchInput.trim().toLowerCase());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const isActiveFilter =
    statusFilter === "all"
      ? undefined
      : statusFilter === "active";

  const usersQuery = useUsers({
    role: roleFilter === "all" ? undefined : roleFilter,
    is_active: isActiveFilter,
    limit: 20,
  });

  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const initiatePasswordReset = useInitiatePasswordReset();

  const allUsers = useMemo(
    () => flattenUserPages(usersQuery.data),
    [usersQuery.data],
  );

  const filteredUsers = useMemo(() => {
    if (!debouncedSearch) return allUsers;
    return allUsers.filter(
      (item) =>
        item.full_name.toLowerCase().includes(debouncedSearch) ||
        item.email.toLowerCase().includes(debouncedSearch),
    );
  }, [allUsers, debouncedSearch]);

  const showToast = useCallback((message: string, variant: "success" | "error" = "success") => {
    setToast({ message, variant });
  }, []);

  const handleCreate = async (values: {
    email: string;
    full_name: string;
    role: UserRole;
    password: string;
  }) => {
    await createUser.mutateAsync(values);
    setFormMode(null);
    showToast("Kullanıcı oluşturuldu.");
  };

  const handleUpdate = async (values: { full_name: string; role: UserRole }) => {
    if (!editingUser) return;
    await updateUser.mutateAsync({
      userId: editingUser.id,
      body: values,
    });
    setFormMode(null);
    setEditingUser(null);
    showToast("Kullanıcı güncellendi.");
  };

  const handleToggleActiveRequest = (user: UserListItem) => {
    if (user.is_active) {
      setToggleTarget(user);
      return;
    }
    void activateUser(user);
  };

  const activateUser = async (user: UserListItem) => {
    try {
      await updateUser.mutateAsync({
        userId: user.id,
        body: { is_active: true },
      });
      showToast("Kullanıcı aktif edildi.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Durum güncellenirken bir hata oluştu.";
      showToast(message, "error");
    }
  };

  const handleDeactivate = async () => {
    if (!toggleTarget) return;

    try {
      await updateUser.mutateAsync({
        userId: toggleTarget.id,
        body: { is_active: false },
      });
      showToast("Kullanıcı pasif yapıldı.");
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Durum güncellenirken bir hata oluştu.";
      showToast(message, "error");
    } finally {
      setToggleTarget(null);
    }
  };

  const handlePasswordReset = async () => {
    if (!editingUser) return;

    try {
      const response = await initiatePasswordReset.mutateAsync({
        user_id: editingUser.id,
      });
      showToast(response.message);
    } catch (error) {
      const message = isApiError(error)
        ? error.message
        : "Şifre sıfırlama bağlantısı gönderilemedi.";
      showToast(message, "error");
      throw error;
    }
  };

  const openCreateModal = () => {
    setEditingUser(null);
    setFormMode("create");
  };

  const openEditModal = (user: UserListItem) => {
    setEditingUser(user);
    setFormMode("edit");
  };

  const closeFormModal = () => {
    setFormMode(null);
    setEditingUser(null);
  };

  const isEmpty =
    !usersQuery.isLoading &&
    !usersQuery.isError &&
    filteredUsers.length === 0;

  const hasNoFilters =
    roleFilter === "all" &&
    statusFilter === "all" &&
    debouncedSearch === "";

  return (
    <RoleGate>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-navy-800">Kullanıcı Yönetimi</h1>
            <p className="mt-1 text-sm text-gray-500">
              Platform kullanıcılarını oluşturun ve yönetin.
            </p>
          </div>
          <Button type="button" onClick={openCreateModal}>
            Kullanıcı Oluştur
          </Button>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <div className="w-full sm:max-w-xs">
            <Input
              label="Ara"
              name="search"
              type="search"
              placeholder="İsim veya e-posta"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="role-filter" className="block text-sm font-medium text-gray-700">
              Rol
            </label>
            <select
              id="role-filter"
              value={roleFilter}
              onChange={(event) =>
                setRoleFilter(event.target.value as RoleFilter)
              }
              className="flex h-10 w-full min-w-[140px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              <option value="all">Tümü</option>
              <option value="admin">Admin</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="status-filter" className="block text-sm font-medium text-gray-700">
              Durum
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value as StatusFilter)
              }
              className="flex h-10 w-full min-w-[140px] rounded-md border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-600"
            >
              <option value="all">Tümü</option>
              <option value="active">Aktif</option>
              <option value="inactive">Pasif</option>
            </select>
          </div>
        </div>

        {usersQuery.isLoading ? <UserTableSkeleton /> : null}

        {usersQuery.isError ? (
          <ErrorView onRetry={() => void usersQuery.refetch()} />
        ) : null}

        {!usersQuery.isLoading && !usersQuery.isError && isEmpty ? (
          <EmptyState
            title="Henüz kullanıcı eklenmemiş"
            description={
              hasNoFilters
                ? "İlk kullanıcıyı oluşturarak başlayın."
                : "Filtrelere uygun kullanıcı bulunamadı."
            }
            action={
              hasNoFilters ? (
                <Button type="button" onClick={openCreateModal}>
                  Kullanıcı Oluştur
                </Button>
              ) : undefined
            }
          />
        ) : null}

        {!usersQuery.isLoading && !usersQuery.isError && filteredUsers.length > 0 ? (
          <>
            <UserTable
              users={filteredUsers}
              currentUserId={currentUser?.id}
              onEdit={openEditModal}
              onToggleActive={handleToggleActiveRequest}
            />

            {usersQuery.hasNextPage ? (
              <div className="flex justify-center">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void usersQuery.fetchNextPage()}
                  disabled={usersQuery.isFetchingNextPage}
                >
                  {usersQuery.isFetchingNextPage
                    ? "Yükleniyor…"
                    : "Daha fazla yükle"}
                </Button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>

      <UserFormModal
        mode={formMode === "edit" ? "edit" : "create"}
        user={editingUser ?? undefined}
        isOpen={formMode !== null}
        isSubmitting={createUser.isPending || updateUser.isPending}
        isPasswordResetLoading={initiatePasswordReset.isPending}
        onClose={closeFormModal}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
        onPasswordReset={formMode === "edit" ? handlePasswordReset : undefined}
      />

      <ConfirmDialog
        isOpen={toggleTarget !== null}
        title="Kullanıcıyı pasif yap"
        message="Bu kullanıcının erişimi kapatılacak. Devam etmek istiyor musunuz?"
        confirmLabel="Pasif Yap"
        isLoading={updateUser.isPending}
        onConfirm={() => void handleDeactivate()}
        onCancel={() => setToggleTarget(null)}
      />

      {toast ? (
        <Toast
          message={toast.message}
          variant={toast.variant}
          onDismiss={() => setToast(null)}
        />
      ) : null}
    </RoleGate>
  );
}
