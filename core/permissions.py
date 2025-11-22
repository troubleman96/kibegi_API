"""Shared permissions for the project"""
from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access it.
    """
    def has_object_permission(self, request, view, obj):
        # Assumes the model has a 'user' or 'owner' field
        return obj.user == request.user if hasattr(obj, 'user') else obj.owner == request.user


class IsLecturer(permissions.BasePermission):
    """
    Permission to only allow lecturers to access.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.user_type == 'lecturer'


class IsStudent(permissions.BasePermission):
    """
    Permission to only allow students to access.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.user_type == 'student'
