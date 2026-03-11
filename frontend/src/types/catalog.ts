export type ApiCamp = {
  id: number;
  name?: string | null;
  lat?: number | null;
  lng?: number | null;
  min_price?: number | null;
  lake_name?: string | null;
  photo_main?: string | null;
  status?: string | null;
  address?: string | null;
  phone?: string | null;
  rooms_count?: number | null;
  description?: string | null;
  housing_type?: string | null;
  emoji_size?: string | null;
  marker_type?: string | null;
  camp_type?: string | null;
  type?: string | null;
  is_vip?: boolean | null;
};

export type ApiRoomPhoto = {
  url: string;
  cover?: boolean | null;
  sort?: number | null;
};

export type ApiRoom = {
  id: number;
  camp_id?: number | null;
  name?: string | null;
  room_type?: string | null;
  floors?: number | null;
  floor?: number | null;
  beds_single?: number | null;
  beds_double?: number | null;
  capacity?: number | null;
  price?: number | null;
  price_adult?: number | null;
  price_child?: number | null;
  photo_main?: string | null;
  description?: string | null;
  available?: boolean | null;
  photos?: ApiRoomPhoto[];
};

export type ApiAvailableRoomsResponse = {
  ok: boolean;
  camp_id: number;
  housing_type: string;
  rooms: ApiRoom[];
};
