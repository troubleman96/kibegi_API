package marketplace

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
	ErrListingNotFound  = errors.New("Listing not found")
	ErrOrderNotFound    = errors.New("Order not found")
	ErrOutOfStock       = errors.New("Requested quantity is not available")
)

type Category struct {
	ID           int64     `json:"id"`
	Name         string    `json:"name"`
	Slug         string    `json:"slug"`
	Description  string    `json:"description"`
	IsActive     bool      `json:"is_active"`
	ListingCount int       `json:"listing_count"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

type User struct {
	ID           int64  `json:"id"`
	Email        string `json:"email"`
	FullName     string `json:"full_name"`
	UserType     string `json:"user_type"`
	ProfileImage any    `json:"profile_image"`
}

type Listing struct {
	ID                uuid.UUID `json:"id"`
	ListingCode       string    `json:"listing_code"`
	Title             string    `json:"title"`
	Description       string    `json:"description"`
	Price             string    `json:"price"`
	Quantity          int       `json:"quantity"`
	SoldQuantity      int       `json:"sold_quantity"`
	AvailableQuantity int       `json:"available_quantity"`
	Condition         string    `json:"condition"`
	Status            string    `json:"status"`
	Image             any       `json:"image"`
	Location          string    `json:"location"`
	CategoryID        *int64    `json:"category"`
	CategoryName      string    `json:"category_name"`
	CategorySlug      string    `json:"category_slug"`
	Seller            User      `json:"seller"`
	CreatedAt         time.Time `json:"created_at"`
	UpdatedAt         time.Time `json:"updated_at"`
}

type Order struct {
	ID         uuid.UUID `json:"id"`
	Listing    Listing   `json:"listing"`
	Buyer      User      `json:"buyer"`
	Seller     User      `json:"seller"`
	Quantity   int       `json:"quantity"`
	UnitPrice  string    `json:"unit_price"`
	TotalPrice string    `json:"total_price"`
	Status     string    `json:"status"`
	CreatedAt  time.Time `json:"created_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type Repository struct{ DB *sql.DB }

func (r Repository) Categories(ctx context.Context, activeOnly bool) ([]Category, error) {
	if r.DB == nil {
		return nil, errors.New("database is not configured")
	}
	where := ""
	if activeOnly {
		where = "WHERE c.is_active = true"
	}
	rows, err := r.DB.QueryContext(ctx, `SELECT c.id, c.name, c.slug, c.description, c.is_active, COUNT(l.id), c.created_at, c.updated_at FROM marketplace_category c LEFT JOIN marketplace_listing l ON l.category_id = c.id AND l.status IN ('active','sold_out') `+where+` GROUP BY c.id ORDER BY c.name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := make([]Category, 0)
	for rows.Next() {
		var item Category
		if err := rows.Scan(&item.ID, &item.Name, &item.Slug, &item.Description, &item.IsActive, &item.ListingCount, &item.CreatedAt, &item.UpdatedAt); err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (r Repository) FindCategory(ctx context.Context, slug string) (Category, error) {
	var item Category
	err := r.DB.QueryRowContext(ctx, `SELECT c.id,c.name,c.slug,c.description,c.is_active,COUNT(l.id),c.created_at,c.updated_at FROM marketplace_category c LEFT JOIN marketplace_listing l ON l.category_id=c.id WHERE c.slug=$1 GROUP BY c.id`, slug).Scan(&item.ID, &item.Name, &item.Slug, &item.Description, &item.IsActive, &item.ListingCount, &item.CreatedAt, &item.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Category{}, ErrCategoryNotFound
	}
	return item, err
}

func (r Repository) Listings(ctx context.Context, userID int64, query, slug, mode string, limit, offset int) ([]Listing, int, error) {
	if r.DB == nil {
		return nil, 0, errors.New("database is not configured")
	}
	filters := []string{"1=1"}
	args := []any{}
	if mode == "me" {
		filters = append(filters, fmt.Sprintf("l.seller_id=$%d", len(args)+1))
		args = append(args, userID)
	} else {
		filters = append(filters, "l.status IN ('active','sold_out')")
	}
	if query != "" {
		filters = append(filters, fmt.Sprintf("(l.title ILIKE $%d OR l.description ILIKE $%d OR l.listing_code ILIKE $%d)", len(args)+1, len(args)+1, len(args)+1))
		args = append(args, "%"+query+"%")
	}
	if slug != "" {
		filters = append(filters, fmt.Sprintf("c.slug=$%d", len(args)+1))
		args = append(args, slug)
	}
	where := strings.Join(filters, " AND ")
	var count int
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM marketplace_listing l LEFT JOIN marketplace_category c ON c.id=l.category_id WHERE `+where, args...).Scan(&count); err != nil {
		return nil, 0, err
	}
	args = append(args, limit, offset)
	rows, err := r.DB.QueryContext(ctx, `SELECT l.id,l.listing_code,l.title,l.description,l.price::text,l.quantity,l.sold_quantity,GREATEST(l.quantity-l.sold_quantity,0),l.condition,l.status,NULLIF(l.image,''),l.location,l.category_id,COALESCE(c.name,''),COALESCE(c.slug,''),l.seller_id,u.email,u.full_name,u.user_type,NULLIF(u.profile_image,''),l.created_at,l.updated_at FROM marketplace_listing l LEFT JOIN marketplace_category c ON c.id=l.category_id JOIN authentication_user u ON u.id=l.seller_id WHERE `+where+` ORDER BY l.created_at DESC LIMIT $`+fmt.Sprint(len(args)-1)+` OFFSET $`+fmt.Sprint(len(args)), args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	items := make([]Listing, 0)
	for rows.Next() {
		item, err := scanListing(rows)
		if err != nil {
			return nil, 0, err
		}
		items = append(items, item)
	}
	return items, count, rows.Err()
}

func (r Repository) FindListing(ctx context.Context, code string) (Listing, error) {
	row := r.DB.QueryRowContext(ctx, `SELECT l.id,l.listing_code,l.title,l.description,l.price::text,l.quantity,l.sold_quantity,GREATEST(l.quantity-l.sold_quantity,0),l.condition,l.status,NULLIF(l.image,''),l.location,l.category_id,COALESCE(c.name,''),COALESCE(c.slug,''),l.seller_id,u.email,u.full_name,u.user_type,NULLIF(u.profile_image,''),l.created_at,l.updated_at FROM marketplace_listing l LEFT JOIN marketplace_category c ON c.id=l.category_id JOIN authentication_user u ON u.id=l.seller_id WHERE l.listing_code=$1`, strings.ToUpper(code))
	item, err := scanListing(row)
	if errors.Is(err, sql.ErrNoRows) {
		return Listing{}, ErrListingNotFound
	}
	return item, err
}

func (r Repository) CreateListing(ctx context.Context, sellerID int64, item Listing) (Listing, error) {
	if item.Title == "" || item.Price == "" || item.Quantity < 1 {
		return Listing{}, errors.New("Invalid listing details")
	}
	id := uuid.New()
	code := strings.ToUpper(uuid.NewString()[:8])
	status := item.Status
	if status == "" {
		status = "active"
	}
	condition := item.Condition
	if condition == "" {
		condition = "good"
	}
	_, err := r.DB.ExecContext(ctx, `INSERT INTO marketplace_listing (id,listing_code,title,description,price,quantity,sold_quantity,condition,status,image,location,created_at,updated_at,category_id,seller_id) VALUES ($1,$2,$3,$4,$5,$6,0,$7,$8,$9,$10,NOW(),NOW(),$11,$12)`, id, code, item.Title, item.Description, item.Price, item.Quantity, condition, status, item.Image, item.Location, item.CategoryID, sellerID)
	if err != nil {
		return Listing{}, err
	}
	return r.FindListing(ctx, code)
}

func (r Repository) UpdateListing(ctx context.Context, sellerID int64, code string, item Listing) (Listing, error) {
	_, err := r.DB.ExecContext(ctx, `UPDATE marketplace_listing SET title=$3,description=$4,price=$5,quantity=$6,condition=$7,location=$8,category_id=$9,updated_at=NOW() WHERE listing_code=$1 AND seller_id=$2`, strings.ToUpper(code), sellerID, item.Title, item.Description, item.Price, item.Quantity, item.Condition, item.Location, item.CategoryID)
	if err != nil {
		return Listing{}, err
	}
	return r.FindListing(ctx, code)
}
func (r Repository) DeleteListing(ctx context.Context, sellerID int64, code string) error {
	result, err := r.DB.ExecContext(ctx, `DELETE FROM marketplace_listing WHERE listing_code=$1 AND seller_id=$2`, strings.ToUpper(code), sellerID)
	if err != nil {
		return err
	}
	n, _ := result.RowsAffected()
	if n == 0 {
		return ErrListingNotFound
	}
	return nil
}

func (r Repository) Purchase(ctx context.Context, buyerID int64, code string, quantity int) (Order, error) {
	if quantity < 1 {
		return Order{}, errors.New("Quantity must be at least 1.")
	}
	tx, err := r.DB.BeginTx(ctx, nil)
	if err != nil {
		return Order{}, err
	}
	defer tx.Rollback()
	var listingID uuid.UUID
	var sellerID int64
	var price string
	var available int
	err = tx.QueryRowContext(ctx, `SELECT id,seller_id,price::text,GREATEST(quantity-sold_quantity,0) FROM marketplace_listing WHERE listing_code=$1 AND status='active' FOR UPDATE`, strings.ToUpper(code)).Scan(&listingID, &sellerID, &price, &available)
	if errors.Is(err, sql.ErrNoRows) {
		return Order{}, ErrListingNotFound
	}
	if err != nil {
		return Order{}, err
	}
	if available < quantity {
		return Order{}, ErrOutOfStock
	}
	var order Order
	err = tx.QueryRowContext(ctx, `UPDATE marketplace_listing SET sold_quantity=sold_quantity+$2,status=CASE WHEN sold_quantity+$2>=quantity THEN 'sold_out' ELSE 'active' END,updated_at=NOW() WHERE id=$1 RETURNING id`, listingID, quantity).Scan(&listingID)
	if err != nil {
		return Order{}, err
	}
	orderID := uuid.New()
	err = tx.QueryRowContext(ctx, `INSERT INTO marketplace_listingorder (id,quantity,unit_price,total_price,status,created_at,updated_at,buyer_id,listing_id,seller_id) VALUES ($1,$2,$3,($3::numeric*$2),'completed',NOW(),NOW(),$4,$5,$6) RETURNING id`, orderID, quantity, price, buyerID, listingID, sellerID).Scan(&order.ID)
	if err != nil {
		return Order{}, err
	}
	if err := tx.Commit(); err != nil {
		return Order{}, err
	}
	return r.FindOrder(ctx, order.ID, buyerID)
}

func (r Repository) Orders(ctx context.Context, userID int64, limit, offset int) ([]Order, int, error) {
	var count int
	if err := r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM marketplace_listingorder WHERE buyer_id=$1 OR seller_id=$1`, userID).Scan(&count); err != nil {
		return nil, 0, err
	}
	rows, err := r.DB.QueryContext(ctx, `SELECT o.id,o.quantity,o.unit_price::text,o.total_price::text,o.status,o.created_at,o.updated_at,l.listing_code,l.title,l.description,l.price::text,l.quantity,l.sold_quantity,GREATEST(l.quantity-l.sold_quantity,0),l.condition,l.status,NULLIF(l.image,''),l.location,l.category_id,COALESCE(c.name,''),COALESCE(c.slug,''),l.seller_id,s.email,s.full_name,s.user_type,NULLIF(s.profile_image,''),o.buyer_id,b.email,b.full_name,b.user_type,NULLIF(b.profile_image,'') FROM marketplace_listingorder o JOIN marketplace_listing l ON l.id=o.listing_id LEFT JOIN marketplace_category c ON c.id=l.category_id JOIN authentication_user s ON s.id=o.seller_id JOIN authentication_user b ON b.id=o.buyer_id WHERE o.buyer_id=$1 OR o.seller_id=$1 ORDER BY o.created_at DESC LIMIT $2 OFFSET $3`, userID, limit, offset)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()
	items := make([]Order, 0)
	for rows.Next() {
		var item Order
		var image, buyerImage sql.NullString
		if err := rows.Scan(&item.ID, &item.Quantity, &item.UnitPrice, &item.TotalPrice, &item.Status, &item.CreatedAt, &item.UpdatedAt, &item.Listing.ListingCode, &item.Listing.Title, &item.Listing.Description, &item.Listing.Price, &item.Listing.Quantity, &item.Listing.SoldQuantity, &item.Listing.AvailableQuantity, &item.Listing.Condition, &item.Listing.Status, &image, &item.Listing.Location, &item.Listing.CategoryID, &item.Listing.CategoryName, &item.Listing.CategorySlug, &item.Listing.Seller.ID, &item.Seller.Email, &item.Seller.FullName, &item.Seller.UserType, &image, &item.Buyer.ID, &item.Buyer.Email, &item.Buyer.FullName, &item.Buyer.UserType, &buyerImage); err != nil {
			return nil, 0, err
		}
		item.Listing.Seller = item.Seller
		if image.Valid {
			item.Listing.Image = image.String
		}
		if buyerImage.Valid {
			item.Buyer.ProfileImage = buyerImage.String
		}
		items = append(items, item)
	}
	return items, count, rows.Err()
}

func (r Repository) FindOrder(ctx context.Context, id uuid.UUID, userID int64) (Order, error) {
	items, count, err := r.Orders(ctx, userID, 1000, 0)
	if err != nil {
		return Order{}, err
	}
	for _, item := range items {
		if item.ID == id {
			return item, nil
		}
	}
	if count == 0 {
		return Order{}, ErrOrderNotFound
	}
	return Order{}, ErrOrderNotFound
}

func scanListing(scanner interface{ Scan(dest ...any) error }) (Listing, error) {
	var item Listing
	var image sql.NullString
	var sellerImage sql.NullString
	err := scanner.Scan(&item.ID, &item.ListingCode, &item.Title, &item.Description, &item.Price, &item.Quantity, &item.SoldQuantity, &item.AvailableQuantity, &item.Condition, &item.Status, &image, &item.Location, &item.CategoryID, &item.CategoryName, &item.CategorySlug, &item.Seller.ID, &item.Seller.Email, &item.Seller.FullName, &item.Seller.UserType, &sellerImage, &item.CreatedAt, &item.UpdatedAt)
	if image.Valid {
		item.Image = image.String
	}
	if sellerImage.Valid {
		item.Seller.ProfileImage = sellerImage.String
	}
	return item, err
}
