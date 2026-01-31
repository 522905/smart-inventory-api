from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of the business.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'owner'


class IsManager(permissions.BasePermission):
    """
    Custom permission to allow owners and managers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['owner', 'manager']


class IsStaff(permissions.BasePermission):
    """
    Custom permission to allow all authenticated staff.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated


class IsSameBusiness(permissions.BasePermission):
    """
    Custom permission to only allow access to objects from the same business.
    """
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'business'):
            return obj.business == request.user.business
        if hasattr(obj, 'business_id'):
            return obj.business_id == request.user.business_id
        return True
