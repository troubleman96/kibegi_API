package library

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

var (
	ErrCategoryNotFound = errors.New("Category not found")
	ErrItemNotFound     = errors.New("Library item not found")
)

type Category struct {
	ID          int64     `json:"id"`
	Name        string    `json:"name"`
	Slug        string    `json:"slug"`
	Description string    `json:"description"`
	IsActive    bool      `json:"is_active"`
	ItemCount   int       `json:"item_count"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}
type User struct {
	ID           int64  `json:"id"`
	Email        string `json:"email"`
	FullName     string `json:"full_name"`
	UserType     string `json:"user_type"`
	ProfileImage any    `json:"profile_image"`
}
type Item struct {
	ID            uuid.UUID `json:"id"`
	ItemCode      string    `json:"item_code"`
	Title         string    `json:"title"`
	Description   string    `json:"description"`
	ObjectName    string    `json:"-"`
	FileName      string    `json:"file_name"`
	FileType      string    `json:"file_type"`
	Subject       string    `json:"subject"`
	CourseCode    string    `json:"course_code"`
	AuthorName    string    `json:"author_name"`
	Status        string    `json:"status"`
	IsFeatured    bool      `json:"is_featured"`
	ViewCount     int       `json:"view_count"`
	DownloadCount int       `json:"download_count"`
	CategoryID    *int64    `json:"-"`
	Category      Category  `json:"category"`
	UploadedBy    User      `json:"uploaded_by"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}
type Repository struct{ DB *sql.DB }

func (r Repository) Categories(ctx context.Context) ([]Category, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT c.id,c.name,c.slug,c.description,c.is_active,COUNT(i.id),c.created_at,c.updated_at FROM library_librarycategory c LEFT JOIN library_libraryitem i ON i.category_id=c.id AND i.status='public' WHERE c.is_active=true GROUP BY c.id ORDER BY c.name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Category, 0)
	for rows.Next() {
		var x Category
		if err := rows.Scan(&x.ID, &x.Name, &x.Slug, &x.Description, &x.IsActive, &x.ItemCount, &x.CreatedAt, &x.UpdatedAt); err != nil {
			return nil, err
		}
		out = append(out, x)
	}
	return out, rows.Err()
}
func (r Repository) Items(ctx context.Context, query, slug, mode string, userID int64, limit, offset int) ([]Item, int, error) {
	filters := []string{"i.status='public'"}
	args := []any{}
	if mode == "me" {
		filters = append(filters, fmt.Sprintf("i.uploaded_by_id=$%d", len(args)+1))
		args = append(args, userID)
	}
	if query != "" {
		filters = append(filters, fmt.Sprintf("(i.title ILIKE $%d OR i.description ILIKE $%d OR i.item_code ILIKE $%d OR i.subject ILIKE $%d)", len(args)+1, len(args)+1, len(args)+1, len(args)+1))
		args = append(args, "%"+query+"%")
	}
	if slug != "" {
		filters = append(filters, fmt.Sprintf("c.slug=$%d", len(args)+1))
		args = append(args, slug)
	}
	where := strings.Join(filters, " AND ")
	var count int
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM library_libraryitem i LEFT JOIN library_librarycategory c ON c.id=i.category_id WHERE `+where, args...).Scan(&count); err != nil {
		return nil, 0, err
	}
	args = append(args, limit, offset)
	rows, err := r.DB.QueryContext(ctx, `SELECT i.id,i.item_code,i.title,i.description,i.file,i.file_type,i.subject,i.course_code,i.author_name,i.status,i.is_featured,i.view_count,i.download_count,i.category_id,COALESCE(c.id,0),COALESCE(c.name,''),COALESCE(c.slug,''),COALESCE(c.description,''),NULLIF(i.file,''),i.uploaded_by_id,u.email,u.full_name,u.user_type,NULLIF(u.profile_image,''),i.created_at,i.updated_at FROM library_libraryitem i LEFT JOIN library_librarycategory c ON c.id=i.category_id JOIN authentication_user u ON u.id=i.uploaded_by_id WHERE `+where+` ORDER BY i.created_at DESC LIMIT $`+fmt.Sprint(len(args)-1)+` OFFSET $`+fmt.Sprint(len(args)), args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	out := make([]Item, 0)
	for rows.Next() {
		x, err := scanItem(rows)
		if err != nil {
			return nil, 0, err
		}
		out = append(out, x)
	}
	return out, count, rows.Err()
}
func (r Repository) Find(ctx context.Context, code string) (Item, error) {
	row := r.DB.QueryRowContext(ctx, `SELECT i.id,i.item_code,i.title,i.description,i.file,i.file_type,i.subject,i.course_code,i.author_name,i.status,i.is_featured,i.view_count,i.download_count,i.category_id,COALESCE(c.id,0),COALESCE(c.name,''),COALESCE(c.slug,''),COALESCE(c.description,''),NULLIF(i.file,''),i.uploaded_by_id,u.email,u.full_name,u.user_type,NULLIF(u.profile_image,''),i.created_at,i.updated_at FROM library_libraryitem i LEFT JOIN library_librarycategory c ON c.id=i.category_id JOIN authentication_user u ON u.id=i.uploaded_by_id WHERE i.item_code=$1`, strings.ToUpper(code))
	x, err := scanItem(row)
	if errors.Is(err, sql.ErrNoRows) {
		return Item{}, ErrItemNotFound
	}
	return x, err
}
func (r Repository) Increment(ctx context.Context, code string, downloads bool) {
	column := "view_count"
	if downloads {
		column = "download_count"
	}
	_, _ = r.DB.ExecContext(ctx, `UPDATE library_libraryitem SET `+column+`=`+column+`+1,updated_at=NOW() WHERE item_code=$1`, strings.ToUpper(code))
}
func scanItem(s interface{ Scan(...any) error }) (Item, error) {
	var x Item
	var image, profile sql.NullString
	err := s.Scan(&x.ID, &x.ItemCode, &x.Title, &x.Description, &x.ObjectName, &x.FileType, &x.Subject, &x.CourseCode, &x.AuthorName, &x.Status, &x.IsFeatured, &x.ViewCount, &x.DownloadCount, &x.CategoryID, &x.Category.ID, &x.Category.Name, &x.Category.Slug, &x.Category.Description, &image, &x.UploadedBy.ID, &x.UploadedBy.Email, &x.UploadedBy.FullName, &x.UploadedBy.UserType, &profile, &x.CreatedAt, &x.UpdatedAt)
	if image.Valid {
		x.FileName = image.String
		parts := strings.Split(image.String, "/")
		x.FileName = parts[len(parts)-1]
	}
	if profile.Valid {
		x.UploadedBy.ProfileImage = profile.String
	}
	return x, err
}

func (r Repository) Create(ctx context.Context, uploadedBy int64, item Item) (Item, error) {
	if item.Title == "" || item.ObjectName == "" {
		return Item{}, errors.New("Title and file are required")
	}
	if item.FileType == "" {
		item.FileType = "other"
	}
	if item.Status == "" {
		item.Status = "public"
	}
	id := uuid.New()
	code := strings.ToUpper(uuid.NewString()[:8])
	_, err := r.DB.ExecContext(ctx, `INSERT INTO library_libraryitem (id,item_code,title,description,file,file_type,subject,course_code,author_name,status,is_featured,view_count,download_count,created_at,updated_at,category_id,uploaded_by_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,false,0,0,NOW(),NOW(),$11,$12)`, id, code, item.Title, item.Description, item.ObjectName, item.FileType, item.Subject, item.CourseCode, item.AuthorName, item.Status, item.CategoryID, uploadedBy)
	if err != nil {
		return Item{}, err
	}
	return r.Find(ctx, code)
}

func (r Repository) Update(ctx context.Context, uploadedBy int64, code string, item Item) (Item, error) {
	_, err := r.DB.ExecContext(ctx, `UPDATE library_libraryitem SET title=$3,description=$4,file_type=$5,subject=$6,course_code=$7,author_name=$8,category_id=$9,updated_at=NOW() WHERE item_code=$1 AND uploaded_by_id=$2`, strings.ToUpper(code), uploadedBy, item.Title, item.Description, item.FileType, item.Subject, item.CourseCode, item.AuthorName, item.CategoryID)
	if err != nil {
		return Item{}, err
	}
	return r.Find(ctx, code)
}

func (r Repository) Delete(ctx context.Context, uploadedBy int64, code string) error {
	result, err := r.DB.ExecContext(ctx, `DELETE FROM library_libraryitem WHERE item_code=$1 AND uploaded_by_id=$2`, strings.ToUpper(code), uploadedBy)
	if err != nil {
		return err
	}
	count, _ := result.RowsAffected()
	if count == 0 {
		return ErrItemNotFound
	}
	return nil
}
