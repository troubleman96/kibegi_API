package storage

import (
	"context"
	"errors"
	"io"
	"net/url"
	"strings"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

var ErrNotConfigured = errors.New("object storage is not configured")

type Config struct {
	Enabled    bool
	Endpoint   string
	AccessKey  string
	SecretKey  string
	Bucket     string
	Secure     bool
	PublicBase string
}

type ObjectStorage struct {
	client     *minio.Client
	bucket     string
	publicBase string
}

func New(cfg Config) (*ObjectStorage, error) {
	if !cfg.Enabled || cfg.Endpoint == "" || cfg.AccessKey == "" || cfg.SecretKey == "" {
		return &ObjectStorage{bucket: cfg.Bucket, publicBase: cfg.PublicBase}, nil
	}
	endpoint := strings.TrimSpace(cfg.Endpoint)
	if parsed, err := url.Parse(endpoint); err == nil && parsed.Host != "" {
		endpoint = parsed.Host
		if parsed.Scheme != "" {
			cfg.Secure = parsed.Scheme == "https"
		}
	} else {
		endpoint = strings.TrimPrefix(strings.TrimPrefix(endpoint, "https://"), "http://")
	}
	client, err := minio.New(endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.AccessKey, cfg.SecretKey, ""),
		Secure: cfg.Secure,
	})
	if err != nil {
		return nil, err
	}
	return &ObjectStorage{client: client, bucket: cfg.Bucket, publicBase: strings.TrimRight(cfg.PublicBase, "/")}, nil
}

func (s *ObjectStorage) Configured() bool {
	return s != nil && s.client != nil && s.bucket != ""
}

func (s *ObjectStorage) Put(ctx context.Context, objectName string, reader io.Reader, size int64, contentType string) (minio.UploadInfo, error) {
	if !s.Configured() {
		return minio.UploadInfo{}, ErrNotConfigured
	}
	return s.client.PutObject(ctx, s.bucket, objectName, reader, size, minio.PutObjectOptions{ContentType: contentType})
}

func (s *ObjectStorage) Open(ctx context.Context, objectName string) (*minio.Object, error) {
	if !s.Configured() {
		return nil, ErrNotConfigured
	}
	object, err := s.client.GetObject(ctx, s.bucket, objectName, minio.GetObjectOptions{})
	if err != nil {
		return nil, err
	}
	return object, nil
}

func (s *ObjectStorage) Stat(ctx context.Context, objectName string) (minio.ObjectInfo, error) {
	if !s.Configured() {
		return minio.ObjectInfo{}, ErrNotConfigured
	}
	return s.client.StatObject(ctx, s.bucket, objectName, minio.StatObjectOptions{})
}

func (s *ObjectStorage) Remove(ctx context.Context, objectName string) error {
	if !s.Configured() {
		return ErrNotConfigured
	}
	return s.client.RemoveObject(ctx, s.bucket, objectName, minio.RemoveObjectOptions{})
}

func (s *ObjectStorage) PublicURL(objectName string) string {
	if s == nil || s.publicBase == "" {
		return ""
	}
	return s.publicBase + "/" + strings.TrimLeft(objectName, "/")
}
